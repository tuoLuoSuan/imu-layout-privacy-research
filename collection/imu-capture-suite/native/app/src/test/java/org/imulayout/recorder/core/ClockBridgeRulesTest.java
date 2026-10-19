package org.imulayout.recorder.core;
import org.junit.Test;
import static org.junit.Assert.*;
import org.json.JSONObject;
public class ClockBridgeRulesTest {
 @Test public void nonnegativePathBoundsAreIntervalsNotMidpoints(){long[] b=ClockBridgeRules.bounds(999000000L,1002000000L,1000000L,1001000L);assertArrayEquals(new long[]{-1000000L,1000000L},b);}
 @Test public void sameNonceAndSessionRequired()throws Exception{JSONObject r=reply();ClockBridgeRules.checkReply(r,"session",0,"nonce",100);r.put("nonce","other");assertThrows(IllegalArgumentException.class,()->ClockBridgeRules.checkReply(r,"session",0,"nonce",100));}
 @Test public void boolTimestampAndUnknownKeysRejected()throws Exception{JSONObject r=reply();r.put("p2_us",true);assertThrows(IllegalArgumentException.class,()->ClockBridgeRules.checkReply(r,"session",0,"nonce",100));JSONObject q=reply();q.put("regions",new JSONObject());assertThrows(IllegalArgumentException.class,()->ClockBridgeRules.checkReply(q,"session",0,"nonce",100));}
 @Test public void reversedOrInconsistentPathsRejected(){assertThrows(IllegalArgumentException.class,()->ClockBridgeRules.bounds(100,90,0,0));assertThrows(IllegalArgumentException.class,()->ClockBridgeRules.bounds(100,200,0,10));}
 private JSONObject reply()throws Exception{return new JSONObject("{\"kind\":\"native_clock_reply\",\"sid\":\"session\",\"seq\":0,\"nonce\":\"nonce\",\"n1_ns\":100,\"p2_us\":1792300000000000,\"p3_us\":1792300000000100,\"watch_sid\":null,\"watch_rows\":0,\"watch_clock_observations\":0,\"watch_finished\":false,\"watch_stop_reason\":null,\"physical_clock_accepted\":false}");}
}
