package com.antigravity.sensoragent.collector

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import com.antigravity.sensoragent.proto.SensorProto.ImuData
import com.antigravity.sensoragent.proto.SensorProto.Vector3

class ImuCollector(
    context: Context,
    private val delay: Int,
    private val onImuSample: (ImuData, Long) -> Unit
) : SensorEventListener {

    private val sensorManager = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
    private val accelSensor = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
    private val gyroSensor = sensorManager.getDefaultSensor(Sensor.TYPE_GYROSCOPE)
    private val linearAccelSensor = sensorManager.getDefaultSensor(Sensor.TYPE_LINEAR_ACCELERATION)

    private val latestAccel = FloatArray(3)
    private val latestGyro = FloatArray(3)
    private val latestLinear = FloatArray(3)

    fun start() {
        accelSensor?.let { sensorManager.registerListener(this, it, delay) }
        gyroSensor?.let { sensorManager.registerListener(this, it, delay) }
        linearAccelSensor?.let { sensorManager.registerListener(this, it, delay) }
    }

    fun stop() {
        sensorManager.unregisterListener(this)
    }

    override fun onSensorChanged(event: SensorEvent?) {
        if (event == null) return

        when (event.sensor.type) {
            Sensor.TYPE_ACCELEROMETER -> {
                System.arraycopy(event.values, 0, latestAccel, 0, 3)
            }
            Sensor.TYPE_GYROSCOPE -> {
                System.arraycopy(event.values, 0, latestGyro, 0, 3)
            }
            Sensor.TYPE_LINEAR_ACCELERATION -> {
                System.arraycopy(event.values, 0, latestLinear, 0, 3)
            }
        }

        // Trigger on gyro or accel updates
        if (event.sensor.type == Sensor.TYPE_GYROSCOPE || event.sensor.type == Sensor.TYPE_ACCELEROMETER) {
            val imu = ImuData.newBuilder()
                .setAccel(Vector3.newBuilder().setX(latestAccel[0]).setY(latestAccel[1]).setZ(latestAccel[2]))
                .setGyro(Vector3.newBuilder().setX(latestGyro[0]).setY(latestGyro[1]).setZ(latestGyro[2]))
                .setLinearAccel(Vector3.newBuilder().setX(latestLinear[0]).setY(latestLinear[1]).setZ(latestLinear[2]))
                .build()

            onImuSample(imu, event.timestamp)
        }
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}
}
