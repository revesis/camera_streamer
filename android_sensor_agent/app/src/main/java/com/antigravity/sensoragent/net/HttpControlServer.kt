package com.antigravity.sensoragent.net

import android.util.Log
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.ServerSocket
import java.net.Socket

class HttpControlServer(
    private val port: Int = 8089,
    private val onSwitchCamera: () -> Boolean,
    private val onGetStatus: () -> String
) {
    private val TAG = "HttpControlServer"
    private var serverSocket: ServerSocket? = null
    @Volatile private var isRunning = false

    fun start() {
        if (isRunning) return
        isRunning = true
        Thread({
            try {
                serverSocket = ServerSocket(port).apply { reuseAddress = true }
                Log.i(TAG, "HTTP Control Server started on port $port")
                while (isRunning) {
                    val client = serverSocket?.accept() ?: break
                    handleClient(client)
                }
            } catch (e: Exception) {
                if (isRunning) Log.e(TAG, "HTTP Server error: ${e.message}")
            }
        }, "HttpControlServer-Acceptor").start()
    }

    private fun handleClient(client: Socket) {
        Thread {
            try {
                client.soTimeout = 3000
                val reader = BufferedReader(InputStreamReader(client.getInputStream()))
                val requestLine = reader.readLine() ?: return@Thread
                val parts = requestLine.split(" ")
                val path = if (parts.size > 1) parts[1] else "/"

                val (statusCode, responseBody) = when {
                    path.startsWith("/switch_camera") -> {
                        val isFront = onSwitchCamera()
                        "200 OK" to "{\"ok\":true,\"is_front_camera\":$isFront}"
                    }
                    path.startsWith("/status") -> {
                        "200 OK" to onGetStatus()
                    }
                    else -> "404 Not Found" to "{\"error\":\"Not Found\"}"
                }

                val bodyBytes = responseBody.toByteArray(Charsets.UTF_8)
                val header = "HTTP/1.1 $statusCode\r\n" +
                        "Content-Type: application/json; charset=utf-8\r\n" +
                        "Access-Control-Allow-Origin: *\r\n" +
                        "Content-Length: ${bodyBytes.size}\r\n" +
                        "Connection: close\r\n\r\n"

                val os = client.getOutputStream()
                os.write(header.toByteArray(Charsets.UTF_8))
                os.write(bodyBytes)
                os.flush()
            } catch (e: Exception) {
                Log.w(TAG, "Client handle error: ${e.message}")
            } finally {
                try { client.close() } catch (e: Exception) {}
            }
        }.start()
    }

    fun stop() {
        isRunning = false
        try {
            serverSocket?.close()
        } catch (e: Exception) {
            Log.w(TAG, "Error closing server socket: ${e.message}")
        }
        serverSocket = null
    }
}
