import app.syncover.patch.IncidentTracker;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
public class TrackerTest {
 static void check(boolean condition) { if(!condition) throw new AssertionError(); }
 public static void main(String[] args) {
  List<String> sent = new ArrayList<>();
  IncidentTracker tracker = new IncidentTracker((folder,message,recovery) -> { sent.add(folder+":"+recovery);return true; });
  tracker.errors("docs",Arrays.asList("file: denied"),0);
  tracker.tick(119999); check(sent.isEmpty());
  tracker.tick(120000); tracker.tick(180000); check(sent.size()==1);
  tracker.block("docs"); tracker.summary("docs","syncing",0,190000);check(sent.size()==1);
  tracker.summary("docs","idle",0,200000);check(sent.size()==2 && tracker.incidents.isEmpty());
  tracker.errors("docs",Arrays.asList("failed"),300000);
  tracker.summary("docs","idle",0,310000);tracker.tick(500000);check(sent.size()==2);
  tracker.errors("docs",Arrays.asList("one"),600000);tracker.tick(720000);check(sent.size()==3);
  tracker.errors("docs",Arrays.asList("two"),730000);tracker.tick(849999);check(sent.size()==3);
  tracker.tick(850000);check(sent.size()==4);
  tracker.errors("docs",Arrays.asList("three"),900000);tracker.block("docs");tracker.tick(1100000);check(sent.size()==4);
  tracker.summary("docs","idle",1,1100000);tracker.tick(1100000);check(sent.size()==5);
  tracker.errors("other",Arrays.asList("failed"),1200000);tracker.stop();tracker.tick(1500000);check(sent.size()==5);
  tracker.errors("other",Arrays.asList("failed"),1500000);tracker.tick(1500000);check(sent.size()==6);
  tracker.errors("paused",Arrays.asList("failed"),1600000);tracker.pause("paused");
  tracker.summary("paused","idle",1,1800000);tracker.tick(1800000);check(sent.size()==6);
  tracker.summary("paused","idle",0,1800000);check(tracker.incidents.containsKey("paused"));
  tracker.resume("paused");tracker.summary("paused","idle",0,1800000);
  IncidentTracker restored = new IncidentTracker((f,m,r) -> {throw new AssertionError("duplicate after restart");});
  restored.incidents.put("other",tracker.incidents.get("other"));restored.stop();
  restored.errors("other",Arrays.asList("failed"),1600000);restored.tick(1800000);
  IncidentTracker retry = new IncidentTracker((f,m,r) -> false);
  retry.errors("x",Arrays.asList("failed"),0);retry.tick(120000);check(!retry.incidents.get("x").alerted);
  System.out.println("PASS: grace period, deduplication, recovery, transient errors, changed errors, pause/retry, stop, persistence and delivery failure");
 }
}
