package app.syncover.patch;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import org.json.JSONArray;
import org.json.JSONObject;
import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

/** Runs on the app's existing events, without another service or wake lock. */
public final class SyncAlerts {
    private static final String TAG = "SyncOver";
    private static final String CHANNEL = "syncover_sync_errors";
    private static final Handler HANDLER = new Handler(Looper.getMainLooper());
    private static SyncAlerts instance;
    private static Field eventType;
    private final Context context;
    private final SharedPreferences prefs;
    private final IncidentTracker tracker;
    private Object owner;
    private final Runnable due = new Runnable() { public void run() { flush(); } };

    private SyncAlerts(Context context) {
        this.context = context.getApplicationContext();
        this.prefs = this.context.getSharedPreferences("syncover_sync_alerts", Context.MODE_PRIVATE);
        this.tracker = new IncidentTracker(new IncidentTracker.Sink() {
            public boolean deliver(String folder, String message, boolean recovery) {
                return notifyUser(folder, message, recovery);
            }
        });
        try {
            JSONObject saved = new JSONObject(prefs.getString("incidents", "{}"));
            Iterator<String> keys = saved.keys();
            while (keys.hasNext()) {
                String folder = keys.next();
                JSONObject value = saved.getJSONObject(folder);
                IncidentTracker.Incident item = new IncidentTracker.Incident();
                item.message = value.optString("message"); item.sent = value.optString("sent");
                item.alerted = value.optBoolean("alerted"); item.since = System.currentTimeMillis();
                tracker.incidents.put(folder, item);
            }
        } catch (Exception e) { Log.w(TAG, "Could not restore alert history", e); }
    }
    public static void onEvent(final Object processor, Object ignoredEvent, Object rawJson) {
        try {
            if (eventType == null) eventType = ignoredEvent.getClass().getField("type");
            String type = String.valueOf(eventType.get(ignoredEvent));
            if (!"FolderErrors".equals(type) && !"FolderSummary".equals(type)
                    && !"StateChanged".equals(type) && !"FolderPaused".equals(type) && !"FolderResumed".equals(type)) return;
        } catch (Exception e) { Log.w(TAG, "Could not identify sync event", e); return; }
        // Convert before dispatch, while Gson's event belongs to this callback.
        final String json = String.valueOf(rawJson);
        HANDLER.post(new Runnable() { public void run() {
            try {
                if (instance == null) {
                    Field field = processor.getClass().getDeclaredField("mContext");
                    field.setAccessible(true);
                    instance = new SyncAlerts((Context) field.get(processor));
                }
                instance.owner = processor;
                instance.event(new JSONObject(json));
            } catch (Exception e) { Log.w(TAG, "Could not process sync event", e); }
        }});
    }
    public static void stopped(final Object processor) {
        HANDLER.post(new Runnable() { public void run() {
            if (instance != null && instance.owner == processor) {
                HANDLER.removeCallbacks(instance.due);
                instance.tracker.stop(); instance.save(); instance.owner = null;
            }
        }});
    }
    private void event(JSONObject event) throws Exception {
        JSONObject data = event.optJSONObject("data");
        if (data == null) return;
        String type = event.optString("type");
        String folder = data.optString("folder", data.optString("id"));
        long now = System.currentTimeMillis();
        if ("FolderErrors".equals(type)) {
            JSONArray errors = data.optJSONArray("errors");
            List<String> lines = new ArrayList<>();
            if (errors != null) for (int i = 0; i < errors.length(); i++) {
                JSONObject error = errors.optJSONObject(i);
                if (error != null && !error.optString("error").isEmpty())
                    lines.add(error.optString("path", "(folder)") + ": " + error.optString("error"));
            }
            tracker.errors(folder, lines, now);
        } else if ("FolderPaused".equals(type)) {
            tracker.pause(folder);
        } else if ("FolderResumed".equals(type)) {
            tracker.resume(folder);
        } else if ("StateChanged".equals(type)) {
            String state = data.optString("to");
            if ("error".equals(state) && !tracker.incidents.containsKey(folder)) {
                List<String> errors = new ArrayList<>();
                errors.add(data.optString("error", "Folder is in an error state"));
                tracker.errors(folder, errors, now);
            } else if ("syncing".equals(state) || "scanning".equals(state)) tracker.block(folder);
        } else if ("FolderSummary".equals(type)) {
            JSONObject summary = data.optJSONObject("summary");
            if (summary != null) {
                // An idle transition alone does not prove errors cleared.
                int count = Math.max(summary.optInt("errors", -1), summary.optInt("pullErrors", -1));
                if (!summary.optString("error").isEmpty()) count = Math.max(count, 1);
                if (count > 0 && !tracker.incidents.containsKey(folder)) {
                    List<String> lines = new ArrayList<>();
                    lines.add(summary.optString("error").isEmpty() ? count + " item(s) failed to sync" : summary.optString("error"));
                    tracker.errors(folder, lines, now);
                }
                tracker.summary(folder, summary.optString("state"), count, now);
            }
        }
        flush();
    }
    private void flush() {
        HANDLER.removeCallbacks(due);
        if (owner == null) return;
        long next = tracker.tick(System.currentTimeMillis());
        save();
        if (next >= 0) HANDLER.postDelayed(due, Math.max(1, next - System.currentTimeMillis()));
    }
    private void save() {
        try {
            JSONObject saved = new JSONObject();
            for (String folder : tracker.incidents.keySet()) {
                IncidentTracker.Incident item = tracker.incidents.get(folder);
                JSONObject value = new JSONObject();
                value.put("message", item.message); value.put("sent", item.sent); value.put("alerted", item.alerted);
                saved.put(folder, value);
            }
            prefs.edit().putString("incidents", saved.toString()).apply();
        } catch (Exception e) { Log.w(TAG, "Could not persist alert history", e); }
    }
    private boolean notifyUser(String folder, String message, boolean recovery) {
        try {
            NotificationManager manager = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
            if (manager == null) return false;
            if (Build.VERSION.SDK_INT >= 24 && !manager.areNotificationsEnabled()) return false;
            if (Build.VERSION.SDK_INT >= 26) {
                manager.createNotificationChannel(new NotificationChannel(CHANNEL, "Sync errors", NotificationManager.IMPORTANCE_DEFAULT));
                if (manager.getNotificationChannel(CHANNEL).getImportance() == NotificationManager.IMPORTANCE_NONE) return false;
            }
            if (message.length() > 4096) message = message.substring(0, 4093) + "...";
            Intent launch = context.getPackageManager().getLaunchIntentForPackage(context.getPackageName());
            Notification.Builder builder = Build.VERSION.SDK_INT >= 26 ? new Notification.Builder(context, CHANNEL) : new Notification.Builder(context);
            int icon = context.getResources().getIdentifier("ic_stat_notify", "drawable", context.getPackageName());
            builder.setSmallIcon(icon != 0 ? icon : android.R.drawable.stat_notify_error)
                .setContentTitle("SyncOver · " + folder + (recovery ? " · Recovered" : ""))
                .setContentText(message).setStyle(new Notification.BigTextStyle().bigText(message))
                .setAutoCancel(true).setVisibility(Notification.VISIBILITY_PRIVATE);
            if (launch != null) builder.setContentIntent(PendingIntent.getActivity(context, 0, launch,
                PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= 23 ? PendingIntent.FLAG_IMMUTABLE : 0)));
            manager.notify("syncover:" + folder, 1, builder.build());
            Log.i(TAG, recovery ? "Recovery notification posted" : "Sync error notification posted");
            return true;
        } catch (Exception e) { Log.w(TAG, "Could not post sync notification", e); return false; }
    }
}
