
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { StyleSheet, View, Image, StatusBar, TouchableOpacity, Modal } from 'react-native';
import { Provider as PaperProvider, TextInput, Button, Text, MD3DarkTheme } from 'react-native-paper';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { PanResponder, Animated } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

const theme = {
  ...MD3DarkTheme,
  colors: { ...MD3DarkTheme.colors, primary: '#00BCD4', background: '#0A0A0A', surface: '#111122' },
};

// ─── Header ──────────────────────────────────────────────────────────────────
function IPHeader({ ip, setIp, connected, onToggle, onDebug }) {
  return (
    <View style={s.header}>
      <TextInput label="PC IP" value={ip} onChangeText={setIp}
        mode="outlined" style={s.ipInput} disabled={connected} dense
        keyboardType="numeric" textColor="#fff"
        outlineColor="#333" activeOutlineColor="#00BCD4"
        autoCorrect={false} blurOnSubmit={false} />
      <Button mode="contained" onPress={onDebug} buttonColor="#FF9800"
        style={[s.connectBtn, { marginRight: 6 }]}
        labelStyle={{ color: '#000', fontSize: 10, fontWeight: 'bold' }}>
        DBG
      </Button>
      <Button mode="contained" onPress={onToggle}
        buttonColor={connected ? '#CF6679' : '#00BCD4'}
        style={s.connectBtn} labelStyle={{ color: '#000', fontWeight: 'bold' }}>
        {connected ? 'STOP' : 'CONNECT'}
      </Button>
    </View>
  );
}

// ─── Mirror Screen ────────────────────────────────────────────────────────────
function MirrorScreen({ ip, setIp }) {
  const [connected,   setConnected]  = useState(false);
  const [imgUrl,      setImgUrl]     = useState(null);
  const [error,       setError]      = useState(null);
  const [alignMode,   setAlignMode]  = useState(false);
  const alignModeRef = useRef(false);
  const [alignToast,  setAlignToast] = useState(false);
  const [translate,   setTranslate]  = useState({ x: 0, y: 0 });
  const [showDebug,   setShowDebug]  = useState(false);
  const [debugImgUrl, setDebugImgUrl] = useState(null);

  // Custom Pan/Zoom state
  const pan = useRef(new Animated.ValueXY({x:0, y:0})).current;
  const scale = useRef(new Animated.Value(1)).current;
  const gestureStateRef = useRef({ initialDistance: null, initialScale: 1, currentScale: 1, currentPan: {x:0, y:0} });

  const interval        = useRef(null);
  const lastId          = useRef(-1);
  const [targetPoint, setTargetPoint] = useState(null);
  const [debugText, setDebugText] = useState('Waiting for tap...');
  // Key fix: measure the TRUE rendered container INSIDE ZoomableView
  const imgContainerRef = useRef({ width: 1, height: 1 });

  // ─── IP persistence ─────────────────────────────────────────────────────────
  useEffect(() => {
    AsyncStorage.getItem('savedIP').then(v => { if (v) setIp(v); }).catch(() => {});
  }, []);
  const handleIpChange = useCallback((val) => {
    setIp(val);
    AsyncStorage.setItem('savedIP', val).catch(() => {});
  }, [setIp]);

  // ─── Alignment ──────────────────────────────────────────────────────────────
  const alignToTarget = useCallback(async (tapX, tapY) => {
    try {
      const clean = ip.replace(/^https?:\/\//, '').split(':')[0];
      const r = await fetch(`http://${clean}:5005/darkest_point`);
      if (!r.ok) {
        setDebugText(`Fetch error: ${r.status}`);
        return;
      }
      const d = await r.json();
      if (!d.ok) {
        setDebugText(`Server error: ${d.error}`);
        return;
      }

      // Skip alignment if server reports low confidence (bad detection)
      if (d.confidence !== undefined && d.confidence < 0.15) {
        console.log('Skipping alignment: low confidence', d.confidence, d.method);
        setTranslate({ x: 0, y: 0 });
        setDebugText(`Skipped (Low Conf): ${d.confidence?.toFixed(2)} (${d.method})`);
        return;
      }

      // Guard: skip if container layout hasn't been measured yet
      const { width: cw, height: ch } = imgContainerRef.current;
      if (cw < 10 || ch < 10) {
        console.log('Skipping alignment: container not measured yet');
        setDebugText(`Skipped (Size < 10): ${cw}x${ch}`);
        return;
      }

      const imgAspect  = d.width / d.height;
      const viewAspect = cw / ch;
      let displayWidth, displayHeight;
      if (imgAspect > viewAspect) {
        displayWidth  = cw;
        displayHeight = cw / imgAspect;
      } else {
        displayHeight = ch;
        displayWidth  = ch * imgAspect;
      }
      // Pixel location of the pupil in the untranslated view
      const baseX = (cw - displayWidth)  / 2 + d.x_pct * displayWidth;
      const baseY = (ch - displayHeight) / 2 + d.y_pct * displayHeight;

      // Compute raw translation
      let tx = tapX - baseX;
      let ty = tapY - baseY;

      // Clamp translation so image never shifts more than 40% off container
      const maxTx = cw * 0.4;
      const maxTy = ch * 0.4;
      tx = Math.max(-maxTx, Math.min(maxTx, tx));
      ty = Math.max(-maxTy, Math.min(maxTy, ty));

      setTranslate({ x: tx, y: ty });
      setDebugText(`Tap: (${tapX.toFixed(0)}, ${tapY.toFixed(0)}) | Size: ${cw.toFixed(0)}x${ch.toFixed(0)} | Pupil: ${baseX.toFixed(0)},${baseY.toFixed(0)} | Trans: ${tx.toFixed(0)},${ty.toFixed(0)} | Conf: ${d.confidence?.toFixed(2)} [${d.method}]`);
    } catch (e) {
      console.log('Align error:', e);
      setDebugText(`Error: ${e.message}`);
    }
  }, [ip]);

  // ─── Re-align when new image or targetPoint changes ──────────────────────────
  useEffect(() => {
    if (imgUrl) {
      if (targetPoint) {
        alignToTarget(targetPoint.x, targetPoint.y);
      } else {
        setTranslate({ x: 0, y: 0 });
      }
    }
  }, [imgUrl, targetPoint, alignToTarget]);

  // PanResponder for smooth dragging and pinching
  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: () => true,
      onPanResponderGrant: () => {
        pan.setOffset({ x: gestureStateRef.current.currentPan.x, y: gestureStateRef.current.currentPan.y });
        pan.setValue({ x: 0, y: 0 });
      },
      onPanResponderMove: (evt, gestureState) => {
        const touches = evt.nativeEvent.touches;
        if (touches.length === 2) {
          // Pinch to zoom
          const dx = touches[0].pageX - touches[1].pageX;
          const dy = touches[0].pageY - touches[1].pageY;
          const distance = Math.sqrt(dx * dx + dy * dy);
          if (!gestureStateRef.current.initialDistance) {
            gestureStateRef.current.initialDistance = distance;
            gestureStateRef.current.initialScale = gestureStateRef.current.currentScale;
          } else {
            let newScale = (distance / gestureStateRef.current.initialDistance) * gestureStateRef.current.initialScale;
            newScale = Math.max(1, Math.min(newScale, 5)); // min 1x, max 5x
            scale.setValue(newScale);
            gestureStateRef.current.currentScale = newScale;
          }
        } else {
          // Reset initialDistance so next 2-finger touch starts fresh
          gestureStateRef.current.initialDistance = null;
          if (touches.length === 1) {
            // Single finger pan
            pan.setValue({ x: gestureState.dx, y: gestureState.dy });
          }
        }
      },
      onPanResponderRelease: (evt, gestureState) => {
        gestureStateRef.current.initialDistance = null;
        pan.flattenOffset();
        gestureStateRef.current.currentPan = { x: pan.x._value, y: pan.y._value };
      },
      onPanResponderTerminate: () => {
        gestureStateRef.current.initialDistance = null;
      }
    })
  ).current;

  // ─── Align tap handler ───────────────────────────────────────────────────────
  const handleAlignTap = useCallback(async (event) => {
    if (!alignModeRef.current) return;
    const { locationX, locationY } = event.nativeEvent;
    setTargetPoint({ x: locationX, y: locationY });

    // Tell the PC server to deactivate align mode
    try {
      const clean = ip.replace(/^https?:\/\//, '').split(':')[0];
      await fetch(`http://${clean}:5005/toggle_align_mode`, { method: 'POST' });
    } catch (e) {
      console.log('Error deactivating align mode:', e);
    }
  }, [ip]);

  // ─── WebSockets ─────────────────────────────────────────────────────────────
  const ws = useRef(null);
  const stop = () => { if (ws.current) { ws.current.close(); ws.current = null; } };
  const start = useCallback(() => {
    stop();
    const clean = ip.replace(/^https?:\/\//, '').split(':')[0];
    const wsUrl = `ws://${clean}:5005/ws`;
    ws.current = new WebSocket(wsUrl);
    ws.current.onopen = () => setError(null);
    ws.current.onmessage = (e) => {
      try {
        const d = JSON.parse(e.data);
        if (d.type === 'status') {
           if (d.align_mode && !alignModeRef.current) {
              setAlignToast(true);
              setTimeout(() => setAlignToast(false), 2000);
           }
           alignModeRef.current = d.align_mode;
           setAlignMode(d.align_mode);
        } else if (d.type === 'image') {
           setImgUrl(`data:image/png;base64,${d.data}`);
           setError(null);
        }
      } catch(err) {}
    };
    ws.current.onerror = (e) => setError('WebSocket error');
    ws.current.onclose = () => {
       // Handle disconnects
    };
  }, [ip]);

  const toggle = useCallback(() => {
    if (connected) {
      stop(); setConnected(false); setImgUrl(null); setError(null);
      targetPoint.current = null; setTranslate({ x: 0, y: 0 });
    } else { start(); setConnected(true); }
  }, [connected, start]);

  useEffect(() => () => stop(), []);

  const openDebug = useCallback(() => {
    const clean = ip.replace(/^https?:\/\//, '').split(':')[0];
    setDebugImgUrl(`http://${clean}:5005/debug_preview?t=${Date.now()}`);
    setShowDebug(true);
  }, [ip]);

  // ─── Render ─────────────────────────────────────────────────────────────────
  return (
    <View style={s.screen}>
      <View style={{ zIndex: 10, elevation: 10 }}>
        <IPHeader ip={ip} setIp={handleIpChange} connected={connected} onToggle={toggle}
           onDebug={openDebug} />
      </View>
      {error && <View style={s.errBanner}><Text style={s.errText}>{error}</Text></View>}

      {/* Debug Modal */}
      <Modal visible={showDebug} transparent animationType="slide" onRequestClose={() => setShowDebug(false)}>
        <View style={s.modalBg}>
          <View style={s.modalBox}>
            <Text style={s.focusText}>🔍 Server Detection Preview</Text>
            <Text style={{ color: '#888', fontSize: 11, marginBottom: 8 }}>
              Red circle = detected pupil center.
            </Text>
            {debugImgUrl && (
              <Image source={{ uri: debugImgUrl }} style={{ width: '100%', height: 280 }} resizeMode="contain" />
            )}
            <Button mode="contained" onPress={() => setShowDebug(false)}
              buttonColor="#CF6679" style={{ marginTop: 12 }} labelStyle={{ color: '#000' }}>
              CLOSE
            </Button>
          </View>
        </View>
      </Modal>

      <View style={s.fill} onLayout={e => {
        imgContainerRef.current = e.nativeEvent.layout;
      }}>
        {imgUrl ? (
          <>
            {/* Translated and Gestured image layer */}
            <View style={[s.fill, { overflow: 'hidden' }]} {...panResponder.panHandlers}>
              <Animated.View style={[s.fill, {
                transform: [
                  { translateX: translate.x },
                  { translateY: translate.y },
                  { translateX: pan.x },
                  { translateY: pan.y },
                  { scale: scale }
                ]
              }]}>
                <Image source={{ uri: imgUrl }} style={s.fill} resizeMode="contain"
                  onError={e => setError(`Img: ${e.nativeEvent.error}`)} />
              </Animated.View>
            </View>

            {/* Green marker at the tapped location */}
            {targetPoint && (
              <View pointerEvents="none" style={{
                position: 'absolute',
                left: targetPoint.x - 5,
                top: targetPoint.y - 5,
                width: 10,
                height: 10,
                borderRadius: 5,
                backgroundColor: '#00ff00',
                borderWidth: 1,
                borderColor: '#000',
                zIndex: 20
              }} />
            )}

            {/* Debug overlay showing values */}
            <View pointerEvents="none" style={{
              position: 'absolute',
              bottom: 10,
              left: 10,
              right: 10,
              backgroundColor: 'rgba(0,0,0,0.8)',
              padding: 8,
              borderRadius: 6,
              zIndex: 30
            }}>
              <Text style={{ color: '#fff', fontSize: 10, fontFamily: 'monospace' }}>
                {debugText}
              </Text>
            </View>

            {/* Touch interceptor ONLY active in align mode */}
            {alignMode && (
              <TouchableOpacity style={StyleSheet.absoluteFill} activeOpacity={1} onPress={handleAlignTap}>
                 <View style={StyleSheet.absoluteFill} pointerEvents="none" />
              </TouchableOpacity>
            )}
            
            {/* Toast popup */}
            {alignToast && (
                <View style={s.focusBanner} pointerEvents="none">
                  <Text style={s.focusText}>🎯 Tap screen to point out center</Text>
                </View>
            )}
          </>
        ) : (
          <View style={s.center}>
            <Text style={s.hint}>
              {connected ? '⏳ Waiting for feed…' : '📡 Enter PC IP and tap CONNECT'}
            </Text>
          </View>
        )}
      </View>
    </View>
  );
}

// ─── Root ─────────────────────────────────────────────────────────────────────
export default function App() {
  const [ip, setIp] = useState('192.168.1.7');
  return (
    <SafeAreaProvider>
      <PaperProvider theme={theme}>
        <SafeAreaView style={s.root}>
          <StatusBar barStyle="light-content" backgroundColor="#0A0A0A" />
          <MirrorScreen ip={ip} setIp={setIp} />
        </SafeAreaView>
      </PaperProvider>
    </SafeAreaProvider>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const s = StyleSheet.create({
  root:   { flex: 1, backgroundColor: '#0A0A0A' },
  screen: { flex: 1, backgroundColor: '#0A0A0A' },
  fill:   { flex: 1 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  header: {
    flexDirection: 'row', padding: 10,
    backgroundColor: '#111122', alignItems: 'center',
    borderBottomWidth: 1, borderBottomColor: '#1E1E3F',
  },
  ipInput:    { flex: 1, marginRight: 6, backgroundColor: '#16213E', height: 46 },
  connectBtn: { height: 46, justifyContent: 'center' },
  errBanner:  { backgroundColor: '#4A0000', padding: 6, alignItems: 'center' },
  errText:    { color: '#FF8A80', fontWeight: 'bold', fontSize: 12 },
  hint:       { color: '#445', fontSize: 15, textAlign: 'center' },
  focusBanner: {
    position: 'absolute', top: 20, left: 20, right: 20,
    backgroundColor: 'rgba(0,0,0,0.85)', padding: 14,
    borderRadius: 10, alignItems: 'center',
    borderWidth: 1, borderColor: '#00BCD4',
  },
  focusText:    { color: '#00BCD4', fontWeight: 'bold', fontSize: 16 },
  focusSubText: { color: '#888', fontSize: 12, marginTop: 4 },
  modalBg:  { flex: 1, backgroundColor: 'rgba(0,0,0,0.85)', justifyContent: 'center', padding: 16 },
  modalBox: { backgroundColor: '#111122', borderRadius: 12, padding: 16, borderWidth: 1, borderColor: '#00BCD4' },
});
