package com.antigravity.sensoragent.net

import android.util.Log
import com.antigravity.sensoragent.proto.SensorProto.ControlPacket
import com.antigravity.sensoragent.proto.SensorProto.SensorPacket
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicLong

class UdpDispatcher(
    private val host: String,
    private val port: Int,
    private val onControlCommand: ((ControlPacket.Command) -> Unit)? = null
) {
    private val TAG = "UdpDispatcher"
    private var socket: DatagramSocket? = null
    private var address: InetAddress? = null
    private val seqCounter = AtomicLong(0)
    private var executor: ExecutorService? = null
    private var receiveThread: Thread? = null

    @Volatile
    private var isConnected = false

    fun start() {
        executor = Executors.newSingleThreadExecutor { r ->
            Thread(r, "Sensor-UDP-Worker").apply { priority = Thread.MAX_PRIORITY }
        }
        executor?.execute {
            try {
                socket = DatagramSocket()
                address = InetAddress.getByName(host)
                isConnected = true
                Log.i(TAG, "UDP Socket successfully bound to $host:$port")

                // Start listening for remote control commands from PC
                startReceiverLoop()
            } catch (e: Exception) {
                Log.e(TAG, "Failed to resolve or bind UDP socket: ${e.message}", e)
                isConnected = false
            }
        }
    }

    private fun startReceiverLoop() {
        receiveThread = Thread({
            val buf = ByteArray(1024)
            val packet = DatagramPacket(buf, buf.size)
            while (isConnected && socket != null && !socket!!.isClosed) {
                try {
                    packet.length = buf.size
                    socket?.receive(packet)
                    val data = packet.data.copyOfRange(packet.offset, packet.offset + packet.length)
                    val ctrl = ControlPacket.parseFrom(data)
                    Log.i(TAG, "Received remote control command: ${ctrl.command}")
                    onControlCommand?.invoke(ctrl.command)
                } catch (e: Exception) {
                    if (!isConnected) break
                }
            }
        }, "Sensor-UDP-Receiver").apply { start() }
    }

    fun nextSequence(): Long {
        return seqCounter.incrementAndGet()
    }

    fun dispatch(packetBuilder: SensorPacket.Builder) {
        if (!isConnected || socket == null || address == null) return

        executor?.execute {
            try {
                val bytes = packetBuilder.build().toByteArray()
                val datagram = DatagramPacket(bytes, bytes.size, address, port)
                socket?.send(datagram)
            } catch (e: Exception) {
                Log.w(TAG, "Error sending UDP packet: ${e.message}")
            }
        }
    }

    fun stop() {
        isConnected = false
        receiveThread?.interrupt()
        receiveThread = null

        executor?.execute {
            try {
                socket?.close()
                socket = null
            } catch (e: Exception) {
                Log.w(TAG, "Error closing socket: ${e.message}")
            }
        }
        executor?.shutdown()
        executor = null
    }
}
