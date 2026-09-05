package org.opennutri.opennutri_app

import android.content.Context
import android.content.Intent
import android.os.SystemClock
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class VoiceWidgetIntentTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()

    // MainActivity intentionally consumes the action by clearing Intent.action.
    // ActivityScenario uses Intent.filterEquals for lifecycle tracking, so it
    // loses this activity after consumption. A class monitor observes the real
    // cold launch without changing production's one-shot intent behavior.
    private fun withActivity(action: String?, test: (MainActivity) -> Unit) {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val monitor = instrumentation.addMonitor(MainActivity::class.java.name, null, false)
        var activity: MainActivity? = null
        try {
            context.startActivity(
                Intent(context, MainActivity::class.java).apply {
                    this.action = action
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
                },
            )
            activity = monitor.waitForActivityWithTimeout(10_000) as? MainActivity
            assertNotNull("The unlocked device must launch the audit activity", activity)
            instrumentation.waitForIdleSync()
            test(activity!!)
        } finally {
            activity?.let { value ->
                instrumentation.runOnMainSync { value.finishAndRemoveTask() }
                awaitCondition { value.isDestroyed }
            }
            instrumentation.removeMonitor(monitor)
        }
    }

    private fun awaitCondition(condition: () -> Boolean) {
        val deadline = SystemClock.uptimeMillis() + 5_000
        var satisfied = false
        while (!satisfied && SystemClock.uptimeMillis() < deadline) {
            instrumentation.runOnMainSync { satisfied = condition() }
            if (!satisfied) SystemClock.sleep(50)
        }
        assertTrue("Activity condition did not complete", satisfied)
    }

    @Test
    fun coldVoiceIntentIsCapturedOnce() {
        withActivity(MainActivity.ACTION_VOICE_LOG) { activity ->
            instrumentation.runOnMainSync {
                assertEquals(1, activity.capturedVoiceActionCount)
                // Flutter may consume first; neither consumer may replay it.
                activity.consumePendingVoiceActionForTest()
                assertFalse(activity.consumePendingVoiceActionForTest())
            }
        }
    }

    @Test
    fun warmVoiceIntentReachesTheSingleTopActivity() {
        withActivity(null) { activity ->
            instrumentation.runOnMainSync {
                assertEquals(0, activity.capturedVoiceActionCount)
                activity.startActivity(
                    Intent(activity, MainActivity::class.java).apply {
                        action = MainActivity.ACTION_VOICE_LOG
                        flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
                    },
                )
            }
            awaitCondition { activity.capturedVoiceActionCount == 1 }
            instrumentation.runOnMainSync {
                assertFalse(activity.isFinishing)
                activity.consumePendingVoiceActionForTest()
                assertFalse(activity.consumePendingVoiceActionForTest())
            }
        }
    }
}
