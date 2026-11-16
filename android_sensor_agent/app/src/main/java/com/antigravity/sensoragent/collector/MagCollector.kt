package com.antigravity.sensoragent.collector

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import com.antigravity.sensoragent.proto.SensorProto.MagnetometerData
import com.antigravity.sensoragent.proto.SensorProto.Vector3

class MagCollector(
    context: Context,
    private val delay: Int,
    private val onMagSample: (MagnetometerData, Long) -> Unit
) : SensorEventListener {

    private val sensorManager = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
    private val magSensor = sensorManager.getDefaultSensor(Sensor.TYPE_MAGNETIC_FIELD)

    fun start() {
        magSensor?.let { sensorManager.registerListener(this, it, delay) }
    }

    fun stop() {
        sensorManager.unregisterListener(this)
    }

    override fun onSensorChanged(event: SensorEvent?) {
        if (event == null || event.sensor.type != Sensor.TYPE_MAGNETIC_FIELD) return

        val mag = MagnetometerData.newBuilder()
            .setMagneticField(
                Vector3.newBuilder()
                    .setX(event.values[0])
                    .setY(event.values[1])
                    .setZ(event.values[2])
            )
            .build()

        onMagSample(mag, event.timestamp)
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}
}
