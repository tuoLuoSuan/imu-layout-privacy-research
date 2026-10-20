package org.imulayout.recorder.core;
import java.util.*;
import org.json.JSONObject;
public final class ClockBridgeRules {
 private ClockBridgeRules(){}
 public static long integer(JSONObject o,String key){Object x=o.opt(key);if(!(x instanceof Long)&&!(x instanceof Integer))throw new IllegalArgumentException("integer required: "+key);return ((Number)x).longValue();}
 public static long[] bounds(long n1,long n4,long p2,long p3){
  if(n1<0||n4<n1||p2<0||p3<p2)throw new IllegalArgumentException("reversed clock bounds");
  long low=Math.subtractExact(n1,Math.multiplyExact(p2,1000L)),high=Math.subtractExact(n4,Math.multiplyExact(p3,1000L));
  if(low>high)throw new IllegalArgumentException("inconsistent algebraic path");return new long[]{low,high};
 }
 public static void checkReply(JSONObject r,String sid,int seq,String nonce,long n1){
  Set<String> expected=new HashSet<>(Arrays.asList("kind","sid","seq","nonce","n1_ns","p2_us","p3_us","watch_sid","watch_rows","watch_clock_observations","watch_finished","watch_failed","watch_failure_stage","watch_stop_reason","physical_clock_accepted"));
  Set<String> legacy=new HashSet<>(Arrays.asList("kind","sid","seq","nonce","n1_ns","p2_us","p3_us","watch_sid","watch_rows","watch_clock_observations","watch_finished","watch_stop_reason","physical_clock_accepted"));
  Set<String> actual=new HashSet<>();Iterator<String> keys=r.keys();while(keys.hasNext())actual.add(keys.next());
  if(!actual.equals(expected)&&!actual.equals(legacy))throw new IllegalArgumentException("unexpected reply fields");
  if(!"native_clock_reply".equals(r.optString("kind"))||!sid.equals(r.optString("sid"))||integer(r,"seq")!=seq||!nonce.equals(r.optString("nonce"))||integer(r,"n1_ns")!=n1)throw new IllegalArgumentException("response identity mismatch");
  if(integer(r,"p2_us")<1000000000000000L||integer(r,"p3_us")<integer(r,"p2_us")||integer(r,"watch_rows")<0||integer(r,"watch_clock_observations")<0)throw new IllegalArgumentException("invalid phone/plugin clocks");
  if(!(r.opt("watch_finished")instanceof Boolean)||!Boolean.FALSE.equals(r.opt("physical_clock_accepted")))throw new IllegalArgumentException("invalid state flags");
  if(r.has("watch_failed")&&!(r.opt("watch_failed")instanceof Boolean))throw new IllegalArgumentException("invalid failure flag");
  Object stage=r.opt("watch_failure_stage");if(stage!=null&&stage!=JSONObject.NULL&&!(stage instanceof String))throw new IllegalArgumentException("invalid failure stage");
  if(Boolean.TRUE.equals(r.opt("watch_failed"))&&!Boolean.TRUE.equals(r.opt("watch_finished")))throw new IllegalArgumentException("failed watch must be finished");
 }
}
