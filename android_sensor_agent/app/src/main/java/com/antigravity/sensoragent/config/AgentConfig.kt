package com.antigravity.sensoragent.config

import android.content.Context
import android.content.SharedPreferences
import android.hardware.SensorManager

class AgentConfig(context: Context) {
    private val prefs: SharedPreferences =
        context.getSharedPreferences("sensor_agent_prefs", Context.MODE_PRIVATE)

    var hostIp: String
        get() = prefs.getString(KEY_HOST_IP, "192.168.1.100") ?: "192.168.1.100"
        set(value) = prefs.edit().putString(KEY_HOST_IP, value).apply()

    var udpPort: Int
        get() = prefs.getInt(KEY_UDP_PORT, 9999)
        set(value) = prefs.edit().putInt(KEY_UDP_PORT, value).apply()

    var enableImu: Boolean
        get() = prefs.getBoolean(KEY_ENABLE_IMU, true)
        set(value) = prefs.edit().putBoolean(KEY_ENABLE_IMU, value).apply()

    var enableOrientation: Boolean
        get() = prefs.getBoolean(KEY_ENABLE_ORIENTATION, true)
        set(value) = prefs.edit().putBoolean(KEY_ENABLE_ORIENTATION, value).apply()

    var enableMag: Boolean
        get() = prefs.getBoolean(KEY_ENABLE_MAG, false)
        set(value) = prefs.edit().putBoolean(KEY_ENABLE_MAG, value).apply()

    var enableCamera: Boolean
        get() = prefs.getBoolean(KEY_ENABLE_CAMERA, false)
        set(value) = prefs.edit().putBoolean(KEY_ENABLE_CAMERA, value).apply()

    var isFrontCamera: Boolean
        get() = prefs.getBoolean(KEY_IS_FRONT_CAMERA, false)
        set(value) = prefs.edit().putBoolean(KEY_IS_FRONT_CAMERA, value).apply()

    var sensorDelay: Int
        get() = prefs.getInt(KEY_SENSOR_DELAY, SensorManager.SENSOR_DELAY_FASTEST)
        set(value) = prefs.edit().putInt(KEY_SENSOR_DELAY, value).apply()

    var isServiceRunning: Boolean
        get() = prefs.getBoolean(KEY_IS_RUNNING, false)
        set(value) = prefs.edit().putBoolean(KEY_IS_RUNNING, value).apply()

    companion object {
        private const val KEY_HOST_IP = "key_host_ip"
        private const val KEY_UDP_PORT = "key_udp_port"
        private const val KEY_ENABLE_IMU = "key_enable_imu"
        private const val KEY_ENABLE_ORIENTATION = "key_enable_orientation"
        private const val KEY_ENABLE_MAG = "key_enable_mag"
        private const val KEY_ENABLE_CAMERA = "key_enable_camera"
        private const val KEY_IS_FRONT_CAMERA = "key_is_front_camera"
        private const val KEY_SENSOR_DELAY = "key_sensor_delay"
        private const val KEY_IS_RUNNING = "key_is_running"
    }
}
