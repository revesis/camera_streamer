package com.antigravity.sensoragent.service

import android.content.Intent
import android.graphics.drawable.Icon
import android.os.Build
import android.service.quicksettings.Tile
import android.service.quicksettings.TileService
import androidx.annotation.RequiresApi
import com.antigravity.sensoragent.R
import com.antigravity.sensoragent.config.AgentConfig

@RequiresApi(Build.VERSION_CODES.N)
class SensorTileService : TileService() {

    private lateinit var config: AgentConfig

    override fun onCreate() {
        super.onCreate()
        config = AgentConfig(this)
    }

    override fun onStartListening() {
        super.onStartListening()
        updateTileState()
    }

    override fun onClick() {
        super.onClick()
        val isRunning = config.isServiceRunning
        if (isRunning) {
            // Stop service
            val intent = Intent(this, SensorForegroundService::class.java).apply {
                action = SensorForegroundService.ACTION_STOP
            }
            startService(intent)
        } else {
            // Start service
            val intent = Intent(this, SensorForegroundService::class.java).apply {
                action = SensorForegroundService.ACTION_START
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(intent)
            } else {
                startService(intent)
            }
        }
        updateTileState()
    }

    private fun updateTileState() {
        val tile = qsTile ?: return
        val isRunning = config.isServiceRunning

        tile.state = if (isRunning) Tile.STATE_ACTIVE else Tile.STATE_INACTIVE
        tile.label = if (isRunning) "推流中" else "传感器流"
        tile.icon = Icon.createWithResource(this, R.drawable.ic_sensor)
        tile.updateTile()
    }
}
