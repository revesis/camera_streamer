package com.antigravity.sensoragent.ui

import android.Manifest
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.hardware.SensorManager
import android.os.BatteryManager
import android.os.Build
import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.antigravity.sensoragent.R
import com.antigravity.sensoragent.collector.BatteryCollector
import com.antigravity.sensoragent.config.AgentConfig
import com.antigravity.sensoragent.databinding.ActivityMainBinding
import com.antigravity.sensoragent.service.SensorForegroundService

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var config: AgentConfig
    private lateinit var batteryCollector: BatteryCollector

    private val batteryReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            updateBatteryUi()
        }
    }

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        val cameraGranted = permissions[Manifest.permission.CAMERA] ?: true
        if (config.enableCamera && !cameraGranted) {
            Toast.makeText(this, "需要相机权限以进行离屏视频采集", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        config = AgentConfig(this)
        batteryCollector = BatteryCollector(this)
        requestRequiredPermissions()
        initViews()
    }

    override fun onResume() {
        super.onResume()
        registerReceiver(batteryReceiver, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        updateUiState()
        updateBatteryUi()
    }

    override fun onPause() {
        super.onPause()
        try {
            unregisterReceiver(batteryReceiver)
        } catch (e: Exception) {
            // ignore
        }
    }

    private fun updateBatteryUi() {
        val status = batteryCollector.getDeviceStatus(config.isFrontCamera)
        val chargingStr = if (status.isCharging) "⚡ 充电中" else "未充电"
        binding.tvBatteryStatus.text = "🔋 手机电量: ${status.batteryLevel}% ($chargingStr) ${status.batteryTemp}℃"
    }

    private fun requestRequiredPermissions() {
        val permissions = mutableListOf<String>()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions.add(Manifest.permission.POST_NOTIFICATIONS)
        }
        if (config.enableCamera) {
            permissions.add(Manifest.permission.CAMERA)
        }
        if (permissions.isNotEmpty()) {
            permissionLauncher.launch(permissions.toTypedArray())
        }
    }

    private fun initViews() {
        // Load saved configs
        binding.etHostIp.setText(config.hostIp)
        binding.etUdpPort.setText(config.udpPort.toString())
        binding.switchImu.isChecked = config.enableImu
        binding.switchOrientation.isChecked = config.enableOrientation
        binding.switchMag.isChecked = config.enableMag
        binding.switchCamera.isChecked = config.enableCamera
        binding.switchFrontCamera.isChecked = config.isFrontCamera

        binding.layoutCameraOptions.visibility = if (config.enableCamera) View.VISIBLE else View.GONE
        binding.switchCamera.setOnCheckedChangeListener { _, isChecked ->
            binding.layoutCameraOptions.visibility = if (isChecked) View.VISIBLE else View.GONE
        }

        binding.switchFrontCamera.setOnCheckedChangeListener { _, isChecked ->
            if (config.isFrontCamera != isChecked) {
                config.isFrontCamera = isChecked
                if (config.isServiceRunning) {
                    val intent = Intent(this, SensorForegroundService::class.java).apply {
                        action = SensorForegroundService.ACTION_SWITCH_CAMERA
                    }
                    startService(intent)
                }
            }
        }

        binding.btnSwitchCamera.setOnClickListener {
            binding.switchFrontCamera.isChecked = !binding.switchFrontCamera.isChecked
            Toast.makeText(this, "已切换镜头为: ${if (config.isFrontCamera) "前置" else "后置"}", Toast.LENGTH_SHORT).show()
        }

        if (config.sensorDelay == SensorManager.SENSOR_DELAY_FASTEST) {
            binding.rbFastest.isChecked = true
        } else {
            binding.rb100Hz.isChecked = true
        }

        // Toggle service button
        binding.btnToggleService.setOnClickListener {
            saveConfigs()
            val isRunning = config.isServiceRunning
            if (isRunning) {
                stopSensorService()
            } else {
                startSensorService()
            }
            updateUiState()
        }
    }



    private fun saveConfigs() {
        config.hostIp = binding.etHostIp.text.toString().trim()
        config.udpPort = binding.etUdpPort.text.toString().toIntOrNull() ?: 9999
        config.enableImu = binding.switchImu.isChecked
        config.enableOrientation = binding.switchOrientation.isChecked
        config.enableMag = binding.switchMag.isChecked
        config.enableCamera = binding.switchCamera.isChecked
        config.isFrontCamera = binding.switchFrontCamera.isChecked
        config.sensorDelay = if (binding.rbFastest.isChecked) {
            SensorManager.SENSOR_DELAY_FASTEST
        } else {
            SensorManager.SENSOR_DELAY_GAME
        }
    }

    private fun startSensorService() {
        config.isServiceRunning = true
        val intent = Intent(this, SensorForegroundService::class.java).apply {
            action = SensorForegroundService.ACTION_START
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }
        Toast.makeText(this, "推流服务已启动，可随时锁屏/熄屏", Toast.LENGTH_SHORT).show()
    }

    private fun stopSensorService() {
        config.isServiceRunning = false
        val intent = Intent(this, SensorForegroundService::class.java).apply {
            action = SensorForegroundService.ACTION_STOP
        }
        startService(intent)
        Toast.makeText(this, "推流服务已停止", Toast.LENGTH_SHORT).show()
    }

    private fun updateUiState() {
        val isRunning = config.isServiceRunning
        if (isRunning) {
            binding.tvStatus.text = getString(R.string.status_running)
            binding.tvStatus.setTextColor(ContextCompat.getColor(this, R.color.accent))
            binding.btnToggleService.text = getString(R.string.btn_stop)
            binding.btnToggleService.setBackgroundColor(ContextCompat.getColor(this, R.color.danger))
        } else {
            binding.tvStatus.text = getString(R.string.status_stopped)
            binding.tvStatus.setTextColor(ContextCompat.getColor(this, R.color.text_secondary))
            binding.btnToggleService.text = getString(R.string.btn_start)
            binding.btnToggleService.setBackgroundColor(ContextCompat.getColor(this, R.color.primary))
        }
    }
}
