package app.syncover.patch;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.Set;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;

/** Pure state machine. Android handles persistence, clocks and delivery. */
public final class IncidentTracker {
    public static final long DELAY_MS = 120000L;
    public interface Sink { boolean deliver(String folder, String message, boolean recovery); }
    public static final class Incident {
        public String message = "";
        public String sent = "";
        public long since;
        public boolean alerted;
        public boolean fresh;
        public boolean blocked;
    }
    public final Map<String, Incident> incidents = new LinkedHashMap<>();
    private final Set<String> paused = new HashSet<>();
    private final Sink sink;
    public IncidentTracker(Sink sink) { this.sink = sink; }

    public void errors(String folder, List<String> errors, long now) {
        if (folder.isEmpty() || errors.isEmpty() || paused.contains(folder)) return;
        StringBuilder joined = new StringBuilder();
        for (String error : new TreeSet<>(errors)) {
            if (joined.length() > 0) joined.append('\n');
            joined.append(error);
        }
        String message = joined.toString();
        Incident item = incidents.get(folder);
        if (item == null) { item = new Incident(); incidents.put(folder, item); }
        if (!message.equals(item.message)) { item.message = message; item.since = now; }
        item.fresh = true;
        item.blocked = false;
    }
    public void pause(String folder) { paused.add(folder); block(folder); }
    public void resume(String folder) { paused.remove(folder); }
    public void block(String folder) {
        Incident item = incidents.get(folder);
        if (item != null) item.blocked = true;
    }
    public void summary(String folder, String state, int errors, long now) {
        if (paused.contains(folder)) return;
        Incident item = incidents.get(folder);
        if ("idle".equals(state) && errors == 0) {
            if (item == null) return;
            if (!item.alerted || sink.deliver(folder, "Syncthing errors cleared.", true)) incidents.remove(folder);
        } else if (errors > 0 && item != null) {
            item.fresh = true;
            item.blocked = "syncing".equals(state) || "scanning".equals(state) || "paused".equals(state);
        } else if ("syncing".equals(state) || "scanning".equals(state) || "paused".equals(state)) block(folder);
    }
    /** Returns next due time, or -1. Failed delivery waits for a later event. */
    public long tick(long now) {
        long next = -1;
        for (Map.Entry<String, Incident> entry : new ArrayList<>(incidents.entrySet())) {
            Incident item = entry.getValue();
            if (!item.fresh || item.blocked || item.message.equals(item.sent)) continue;
            long due = item.since + DELAY_MS;
            if (now >= due) {
                if (sink.deliver(entry.getKey(), item.message, false)) {
                    item.sent = item.message;
                    item.alerted = true;
                }
            } else if (next < 0 || due < next) next = due;
        }
        return next;
    }
    public void stop() { for (Incident item : incidents.values()) item.fresh = false; }
}
