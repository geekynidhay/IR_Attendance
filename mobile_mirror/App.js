
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { StyleSheet, View, Image, StatusBar, TouchableOpacity, Modal } from 'react-native';
import { Provider as PaperProvider, TextInput, Button, Text, MD3DarkTheme } from 'react-native-paper';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { ReactNativeZoomableView } from '@dudigital/react-native-zoomable-view';
import AsyncStorage from '@react-native-async-storage/async-storage';

const theme = {
  ...MD3DarkTheme,
  colors: { ...MD3DarkTheme.colors, primary: '#00BCD4', background: '#0A0A0A', surface: '#111122' },
};

// ─── Header ──────────────────────────────────────────────────────────────────
function IPHeader({ ip, setIp, connected, onToggle, focusMode, setFocusMode, onDebug }) {
  return (
    <View style={s.header}>
      <TextInput label="PC IP" value={ip} onChangeText={setIp}
        mode="outlined" style={s.ipInput} disabled={connected} dense
        keyboardType="numeric" textColor="#fff"
        outlineColor="#333" activeOutlineColor="#00BCD4"
        autoCorrect={false} blurOnSubmit={false} />
      <Button mode="contained" onPress={() => setFocusMode(!focusMode)}
        buttonColor={focusMode ? '#4CAF50' : '#444'}
        style={[s.connectBtn, { marginRight: 6 }]}
        labelStyle={{ color: '#fff', fontSize: 11, fontWeight: 'bold' }}>
        {focusMode ? '🎯 ON' : '🎯 OFF'}
      </Button>
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
  const [focusMode,   setFocusMode]  = useState(false);
  const [translate,   setTranslate]  = useState({ x: 0, y: 0 });
  const [showDebug,   setShowDebug]  = useState(false);
  const [debugImgUrl, setDebugImgUrl] = useState(null);

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

  // ─── Focus tap handler ───────────────────────────────────────────────────────
  const handleFocusTap = useCallback((event) => {
    const { locationX, locationY } = event.nativeEvent;
    setTargetPoint({ x: locationX, y: locationY });
    setFocusMode(false);
  }, []);

  // ─── Polling ────────────────────────────────────────────────────────────────
  const stop = () => { clearInterval(interval.current); interval.current = null; };
  const start = useCallback(() => {
    stop();
    interval.current = setInterval(async () => {
      const clean = ip.replace(/^https?:\/\//, '').split(':')[0];
      try {
        const c = new AbortController();
        const t = setTimeout(() => c.abort(), 2000);
        const r = await fetch(`http://${clean}:5005/status`, { signal: c.signal });
        clearTimeout(t);
        if (r.ok) {
          const d = await r.json();
          if (d.image_id !== lastId.current) {
            lastId.current = d.image_id;
            setImgUrl(`http://${clean}:5005/image?t=${Date.now()}`);
            setError(null);
          }
        }
      } catch (e) { if (e.name !== 'AbortError') setError('Network error'); }
    }, 500);
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
          focusMode={focusMode} setFocusMode={setFocusMode} onDebug={openDebug} />
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
            {/* Translated image layer */}
            <View style={[s.fill, {
              overflow: 'hidden',
              transform: [{ translateX: translate.x }, { translateY: translate.y }]
            }]}>
              <ReactNativeZoomableView maxZoom={100} minZoom={0.01} initialZoom={1}
                bindToBorders={false} style={s.fill}>
                <View style={s.fill}>
                  <Image source={{ uri: imgUrl }} style={s.fill} resizeMode="contain"
                    onError={e => setError(`Img: ${e.nativeEvent.error}`)} />
                </View>
              </ReactNativeZoomableView>
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

            {/* Focus overlay — conditionally rendered = ZERO interference when off */}
            {focusMode && (
              <TouchableOpacity style={StyleSheet.absoluteFill} activeOpacity={1}
                onPress={handleFocusTap}>
                <View style={s.focusBanner} pointerEvents="none">
                  <Text style={s.focusText}>🎯 Tap exactly on the pupil center</Text>
                  <Text style={s.focusSubText}>All future images auto-align to this spot</Text>
                </View>
              </TouchableOpacity>
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
