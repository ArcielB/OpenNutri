package org.opennutri.opennutri_app

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews

class VoiceLogWidgetProvider : AppWidgetProvider() {
    override fun onUpdate(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetIds: IntArray,
    ) {
        appWidgetIds.forEach { appWidgetId ->
            val intent =
                Intent(context, MainActivity::class.java).apply {
                    action = MainActivity.ACTION_VOICE_LOG
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
                }
            val pendingIntent =
                PendingIntent.getActivity(
                    context,
                    appWidgetId,
                    intent,
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
                )
            val views =
                RemoteViews(context.packageName, R.layout.voice_log_widget).apply {
                    setOnClickPendingIntent(R.id.voice_widget_button, pendingIntent)
                    setContentDescription(R.id.voice_widget_button, "Log food by voice")
                }
            appWidgetManager.updateAppWidget(appWidgetId, views)
        }
    }
}
