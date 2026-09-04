package org.opennutri.opennutri_app

import android.appwidget.AppWidgetManager
import android.content.ComponentName
import android.content.Intent
import android.os.Build
import android.widget.Toast
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    companion object {
        const val ACTION_VOICE_LOG = "org.opennutri.opennutri_app.ACTION_VOICE_LOG"
        private const val CHANNEL = "org.opennutri.app/voice_widget"
    }

    private var methodChannel: MethodChannel? = null
    private var pendingVoiceAction = false

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        methodChannel =
            MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL).also { channel ->
                channel.setMethodCallHandler { call, result ->
                    when (call.method) {
                        "consumePendingVoiceAction" -> result.success(consumePendingVoiceAction())
                        "requestPinVoiceWidget" -> result.success(requestPinVoiceWidget())
                        "finishQuickCapture" -> {
                            val count = call.argument<Int>("foodCount") ?: 0
                            val needsReview = call.argument<Boolean>("needsReview") ?: false
                            finishQuickCapture(count, needsReview)
                            result.success(null)
                        }
                        else -> result.notImplemented()
                    }
                }
            }
        captureVoiceAction(intent, notifyFlutter = false)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        captureVoiceAction(intent, notifyFlutter = true)
    }

    private fun captureVoiceAction(intent: Intent?, notifyFlutter: Boolean) {
        if (intent?.action != ACTION_VOICE_LOG) return
        pendingVoiceAction = true
        intent.action = null
        if (notifyFlutter) {
            methodChannel?.invokeMethod("voiceLogRequested", null)
        }
    }

    private fun consumePendingVoiceAction(): Boolean {
        captureVoiceAction(intent, notifyFlutter = false)
        val pending = pendingVoiceAction
        pendingVoiceAction = false
        return pending
    }

    private fun requestPinVoiceWidget(): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return false
        val manager = AppWidgetManager.getInstance(this)
        if (!manager.isRequestPinAppWidgetSupported) return false
        return manager.requestPinAppWidget(
            ComponentName(this, VoiceLogWidgetProvider::class.java),
            null,
            null,
        )
    }

    private fun finishQuickCapture(foodCount: Int, needsReview: Boolean) {
        val noun = if (foodCount == 1) "food" else "foods"
        val suffix = if (needsReview) " · tap OpenNutri to review" else ""
        Toast.makeText(this, "$foodCount $noun logged$suffix", Toast.LENGTH_LONG).show()
        finishAndRemoveTask()
    }

    internal fun consumePendingVoiceActionForTest(): Boolean = consumePendingVoiceAction()
}
