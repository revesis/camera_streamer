package com.antigravity.sensoragent.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.util.Log
import androidx.core.app.NotificationCompat
import com.antigravity.sensoragent.R
import com.antigravity.sensoragent.collector.BatteryCollector
import com.antigravity.sensoragent.collector.CameraCollector
import com.antigravity.sensoragent.collector.ImuCollector
import com.antigravity.sensoragent.collector.MagCollector
import com.antigravity.sensoragent.collector.OrientationCollector
import com.antigravity.sensoragent.config.AgentConfig
import com.antigravity.sensoragent.net.HttpControlServer
import com.antigravity.sensoragent.net.UdpDispatcher
import com.antigravity.sensoragent.proto.SensorProto.CameraFrame
import com.antigravity.sensoragent.proto.SensorProto.ControlPacket
import com.antigravity.sensoragent.proto.SensorProto.SensorPacket
import com.antigravity.sensoragent.ui.MainActivity
import com.google.protobuf.ByteString
import java.util.concurrent.atomic.AtomicInteger

class SensorForegroundService : Service() {

    private val TAG = "SensorForegroundService"
    private val CHANNEL_ID = "sensor_stream_channel"
    private val NOTIFICATION_ID = 1001

    private var wakeLock: PowerManager.WakeLock? = null
    private var udpDispatcher: UdpDispatcher? = null

    private var imuCollector: ImuCollector? = null
    private var orientationCollector: OrientationCollector? = null
    private var magCollector: MagCollector? = null
    private var cameraCollector: CameraCollector? = null
    private var batteryCollector: BatteryCollector? = null
    private var httpControlServer: HttpControlServer? = null
    private val frameIdCounter = AtomicInteger(0)

    private lateinit var config: AgentConfig
    private val batteryHandler = Handler(Looper.getMainLooper())
    private val batteryRunnable = object : Runnable {
        override fun run() {
            sendDeviceStatus()
            batteryHandler.postDelayed(this, 2000L)
        }
    }

    private val controlReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action == ACTION_SWITCH_CAMERA) {
                Log.i(TAG, "ACTION_SWITCH_CAMERA received via broadcast")
                handleSwitchCamera()
            }
        }
    }

    override fun onCreate() {
        super.onCreate()
        config = AgentConfig(this)
        batteryCollector = BatteryCollector(this)
        createNotificationChannel()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(controlReceiver, IntentFilter(ACTION_SWITCH_CAMERA), Context.RECEIVER_EXPORTED)
        } else {
            registerReceiver(controlReceiver, IntentFilter(ACTION_SWITCH_CAMERA))
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val action = intent?.action
        if (action == ACTION_STOP) {
            stopStreaming()
            stopSelf()
            return START_NOT_STICKY
        } else if (action == ACTION_SWITCH_CAMERA) {
            handleSwitchCamera()
            return START_STICKY
        }

        startStreaming()
        return START_STICKY
    }

    private fun handleSwitchCamera() {
        if (cameraCollector != null) {
            cameraCollector?.switchCamera()
            config.isFrontCamera = cameraCollector?.isFrontCamera ?: false
        } else {
            config.isFrontCamera = !config.isFrontCamera
        }
        sendDeviceStatus()
    }

    private fun sendDeviceStatus() {
        val isFront = cameraCollector?.isFrontCamera ?: config.isFrontCamera
        val status = batteryCollector?.getDeviceStatus(isFront) ?: return
        val deviceId = "${Build.MANUFACTURER} ${Build.MODEL}"
        val builder = SensorPacket.newBuilder()
            .setSequenceNumber(udpDispatcher?.nextSequence() ?: 0L)
            .setTimestampNs(System.nanoTime())
            .setDeviceId(deviceId)
            .setDeviceStatus(status)
        udpDispatcher?.dispatch(builder)
    }

    private fun startStreaming() {
        Log.i(TAG, "Starting SensorForegroundService in background...")

        // 1. Acquire WakeLock
        val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = powerManager.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            "SensorAgent::CpuKeepAlive"
        ).apply {
            acquire(24 * 60 * 60 * 1000L) // 24 hours max
        }

        // 2. Start Foreground Notification
        val notification = createNotification()
        startForeground(NOTIFICATION_ID, notification)

        // 3. Initialize UDP Dispatcher with Control Command Callback
        udpDispatcher = UdpDispatcher(config.hostIp, config.udpPort) { cmd ->
            when (cmd) {
                ControlPacket.Command.SWITCH_CAMERA -> {
                    Log.i(TAG, "Remote SWITCH_CAMERA received via UDP")
                    batteryHandler.post { handleSwitchCamera() }
                }
                else -> {}
            }
        }.apply {
            start()
        }

        val deviceId = "${Build.MANUFACTURER} ${Build.MODEL}"

        // 4. Start Enabled Collectors
        if (config.enableImu) {
            imuCollector = ImuCollector(this, config.sensorDelay) { imuData, timestampNs ->
                val builder = SensorPacket.newBuilder()
                    .setSequenceNumber(udpDispatcher?.nextSequence() ?: 0L)
                    .setTimestampNs(timestampNs)
                    .setDeviceId(deviceId)
                    .setImu(imuData)
                udpDispatcher?.dispatch(builder)
            }.apply { start() }
        }

        if (config.enableOrientation) {
            orientationCollector = OrientationCollector(this, config.sensorDelay) { orientationData, timestampNs ->
                val builder = SensorPacket.newBuilder()
                    .setSequenceNumber(udpDispatcher?.nextSequence() ?: 0L)
                    .setTimestampNs(timestampNs)
                    .setDeviceId(deviceId)
                    .setOrientation(orientationData)
                udpDispatcher?.dispatch(builder)
            }.apply { start() }
        }

        if (config.enableMag) {
            magCollector = MagCollector(this, config.sensorDelay) { magData, timestampNs ->
                val builder = SensorPacket.newBuilder()
                    .setSequenceNumber(udpDispatcher?.nextSequence() ?: 0L)
                    .setTimestampNs(timestampNs)
                    .setDeviceId(deviceId)
                    .setMag(magData)
                udpDispatcher?.dispatch(builder)
            }.apply { start() }
        }

        if (config.enableCamera) {
            cameraCollector = CameraCollector(this, config.isFrontCamera) { frameBytes, timestampNs ->
                val chunkSize = 1100
                val totalChunks = (frameBytes.size + chunkSize - 1) / chunkSize
                val frameId = frameIdCounter.incrementAndGet()

                for (chunkIdx in 0 until totalChunks) {
                    val offset = chunkIdx * chunkSize
                    val length = minOf(chunkSize, frameBytes.size - offset)
                    val chunkPayload = ByteString.copyFrom(frameBytes, offset, length)

                    val cameraFrame = CameraFrame.newBuilder()
                        .setWidth(640)
                        .setHeight(480)
                        .setFormat(CameraFrame.Format.JPEG)
                        .setPayload(chunkPayload)
                        .setChunkIndex(chunkIdx)
                        .setTotalChunks(totalChunks)
                        .setFrameId(frameId)
                        .build()

                    val builder = SensorPacket.newBuilder()
                        .setSequenceNumber(udpDispatcher?.nextSequence() ?: 0L)
                        .setTimestampNs(timestampNs)
                        .setDeviceId(deviceId)
                        .setCameraFrame(cameraFrame)
                    udpDispatcher?.dispatch(builder)
                }
            }.apply { start() }
        }

        // Start periodic battery status reporting
        batteryHandler.removeCallbacks(batteryRunnable)
        batteryHandler.post(batteryRunnable)

        // Start direct HTTP control server on port 8089
        httpControlServer = HttpControlServer(
            port = 8089,
            onSwitchCamera = {
                batteryHandler.post { handleSwitchCamera() }
                !config.isFrontCamera
            },
            onGetStatus = {
                val isFront = cameraCollector?.isFrontCamera ?: config.isFrontCamera
                val status = batteryCollector?.getDeviceStatus(isFront)
                "{\"ok\":true,\"battery_level\":${status?.batteryLevel ?: -1},\"is_charging\":${status?.isCharging ?: false},\"battery_temp\":${status?.batteryTemp ?: 0f},\"is_front_camera\":$isFront,\"device_id\":\"${Build.MANUFACTURER} ${Build.MODEL}\"}"
            }
        ).apply { start() }

        config.isServiceRunning = true
    }

    private fun stopStreaming() {
        Log.i(TAG, "Stopping SensorForegroundService...")
        batteryHandler.removeCallbacks(batteryRunnable)

        imuCollector?.stop()
        imuCollector = null

        orientationCollector?.stop()
        orientationCollector = null

        magCollector?.stop()
        magCollector = null

        cameraCollector?.stop()
        cameraCollector = null

        httpControlServer?.stop()
        httpControlServer = null

        udpDispatcher?.stop()
        udpDispatcher = null

        wakeLock?.let {
            if (it.isHeld) it.release()
        }
        wakeLock = null

        config.isServiceRunning = false
    }

    override fun onDestroy() {
        try {
            unregisterReceiver(controlReceiver)
        } catch (e: Exception) {
            // ignore
        }
        stopStreaming()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Sensor Stream Service",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Keeps sensor streaming alive during physical screen off."
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    private fun createNotification(): Notification {
        val launchIntent = Intent(this, MainActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            launchIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        val stopIntent = Intent(this, SensorForegroundService::class.java).apply {
            action = ACTION_STOP
        }
        val stopPendingIntent = PendingIntent.getService(
            this,
            1,
            stopIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("传感器推流中 (${config.hostIp}:${config.udpPort})")
            .setContentText("后台低功耗运行中，屏幕熄灭保持采样")
            .setSmallIcon(R.drawable.ic_sensor)
            .setContentIntent(pendingIntent)
            .addAction(R.drawable.ic_sensor, "停止", stopPendingIntent)
            .setOngoing(true)
            .build()
    }

    companion object {
        const val ACTION_START = "com.antigravity.sensoragent.START"
        const val ACTION_STOP = "com.antigravity.sensoragent.STOP"
        const val ACTION_SWITCH_CAMERA = "com.antigravity.sensoragent.SWITCH_CAMERA"
    }
}
