package org.opennutri.opennutri_app

import android.content.Intent
import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class VoiceWidgetIntentTest {
    @Test
    fun coldVoiceIntentIsRetainedUntilFlutterConsumesIt() {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val intent =
            Intent(context, MainActivity::class.java).apply {
                action = MainActivity.ACTION_VOICE_LOG
            }
        ActivityScenario.launch<MainActivity>(intent).use { scenario ->
            scenario.onActivity { activity ->
                assertTrue(activity.consumePendingVoiceActionForTest())
            }
        }
    }

    @Test
    fun warmVoiceIntentReachesTheSingleTopActivity() {
        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            scenario.onActivity { activity ->
                activity.startActivity(
                    Intent(activity, MainActivity::class.java).apply {
                        action = MainActivity.ACTION_VOICE_LOG
                        flags =
                            Intent.FLAG_ACTIVITY_SINGLE_TOP or
                                Intent.FLAG_ACTIVITY_CLEAR_TOP
                    },
                )
            }
            InstrumentationRegistry.getInstrumentation().waitForIdleSync()
            scenario.onActivity { activity ->
                assertTrue(activity.consumePendingVoiceActionForTest())
            }
        }
    }
}
