package com.antigravity.sensoragent.collector

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import com.antigravity.sensoragent.proto.SensorProto.OrientationData
import com.antigravity.sensoragent.proto.SensorProto.Quaternion
import com.antigravity.sensoragent.proto.SensorProto.Vector3

class OrientationCollector(
    context: Context,
    private val delay: Int,
    private val onOrientationSample: (OrientationData, Long) -> Unit
) : SensorEventListener {

    private val sensorManager = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
    private val rotationSensor = sensorManager.getDefaultSensor(Sensor.TYPE_ROTATION_VECTOR)

    private val rotationMatrix = FloatArray(9)
    private val orientationAngles = FloatArray(3)
    private val quaternionValues = FloatArray(4)

    fun start() {
        rotationSensor?.let { sensorManager.registerListener(this, it, delay) }
    }

    fun stop() {
        sensorManager.unregisterListener(this)
    }

    override fun onSensorChanged(event: SensorEvent?) {
        if (event == null || event.sensor.type != Sensor.TYPE_ROTATION_VECTOR) return

        SensorManager.getQuaternionFromVector(quaternionValues, event.values)
        SensorManager.getRotationMatrixFromVector(rotationMatrix, event.values)
        SensorManager.getOrientation(rotationMatrix, orientationAngles)

        val quat = Quaternion.newBuilder()
            .setW(quaternionValues[0])
            .setX(quaternionValues[1])
            .setY(quaternionValues[2])
            .setZ(quaternionValues[3])
            .build()

        val euler = Vector3.newBuilder()
            .setX(Math.toDegrees(orientationAngles[1].toDouble()).toFloat()) // Pitch
            .setY(Math.toDegrees(orientationAngles[2].toDouble()).toFloat()) // Roll
            .setZ(Math.toDegrees(orientationAngles[0].toDouble()).toFloat()) // Azimuth / Yaw
            .build()

        val orientation = OrientationData.newBuilder()
            .setRotationVector(quat)
            .setEulerAngles(euler)
            .build()

        onOrientationSample(orientation, event.timestamp)
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}
}
