import React, { useState, useEffect, useRef, useCallback } from 'react';
import { StyleSheet, View, Image, StatusBar, TouchableOpacity, Text, TextInput, KeyboardAvoidingView, Platform, Keyboard } from 'react-native';
import { Provider as PaperProvider, MD3DarkTheme } from 'react-native-paper';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { ReactNativeZoomableView } from '@dudigital/react-native-zoomable-view';
import AsyncStorage from '@react-native-async-storage/async-storage';

const theme = { ...MD3DarkTheme, colors: { ...MD3DarkTheme.colors, primary: '#00BCD4', background: '#0A0A0A' } };

// --- Header Component ---
const IPHeader = ({ ip, setIp, connected, onToggle, focusMode, setFocusMode, autoDiscover }) => {
  return (
    <View style={s.header}>
      <View style={s.ipInputContainer}>
        <TextInput
          style={s.ipInputText}
          value={ip}
          onChangeText={setIp}
          placeholder="192.168.1.X"
          placeholderTextColor="#888"
          keyboardType="numeric"
        />
      </View>
      <View style={s.controlsRow}>
        <TouchableOpacity 
          style={s.smallBtn}
          onPress={autoDiscover}
        >
          <Text style={s.smallBtnText}>A</Text>
        </TouchableOpacity>
        
        <TouchableOpacity 
          style={[s.smallBtn, focusMode ? s.smallBtnActive : null]}
          onPress={() => setFocusMode(!focusMode)}
        >
          <Text style={s.smallBtnText}>{focusMode ? 'X' : 'F'}</Text>
        </TouchableOpacity>
        
        <TouchableOpacity 
          style={[s.smallBtn, connected ? s.smallBtnStop : s.smallBtnStart]}
          onPress={onToggle}
        >
          <Text style={s.smallBtnText}>{connected ? '■' : '▶'}</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
};

// --- Main Mirror Screen ---
function MirrorScreen({ ip, setIp }) {
  const [connected, setConnected] = useState(false);
  const [imgUrl, setImgUrl] = useState(null);
  const [error, setError] = useState(null);
  const [focusMode, setFocusMode] = useState(false);
  const [translate, setTranslate] = useState({ x: 0, y: 0 });
  
  const ipRef = useRef(ip);
  useEffect(() => { ipRef.current = ip; }, [ip]);

  const interval = useRef(null);
  const lastId = useRef(-1);
  const [targetPoint, setTargetPoint] = useState(null);
  const zoomStateRef = useRef({ zoomLevel: 1, offsetX: 0, offsetY: 0 });
  const [pupilPoint, setPupilPoint] = useState(null);
  const [minZoom, setMinZoom] = useState(0.01);
  const imgContainerRef = useRef({ width: 1, height: 1 });

  useEffect(() => {
    AsyncStorage.getItem('savedIP').then(v => { 
      if (v && v !== 'Scanning...') setIp(v); 
      else autoDiscover();
    }).catch(() => autoDiscover());
  }, []);


  // --- Auto-Discovery Logic via Firebase ---
  const autoDiscover = useCallback(async () => {
    setIp('Scanning...');
    setError(null);
    stop();
    setConnected(false);
    
    try {
      const res = await fetch('https://attendance-68878-default-rtdb.asia-southeast1.firebasedatabase.app/active_pc_ip.json');
      if (res.ok) {
        const data = await res.json();
        if (data && data.ip) {
          setIp(data.ip);
          // Auto-start immediately after finding it
          setTimeout(() => {
            start();
            setConnected(true);
          }, 300);
          return;
        }
      }
      throw new Error('No IP found');
    } catch (e) {
      setIp('192.168.1.');
      setError('Auto-discovery failed. Ensure PC app is running and has internet.');
    }
  }, [start, stop]);
  
  // Auto-scan on mount if no saved IP, or just provide a button

  const handleIpChange = useCallback((val) => {
    setIp(val);
    AsyncStorage.setItem('savedIP', val).catch(() => {});
  }, []);

  // Sync pupil point from PC
  useEffect(() => {
    if (!connected) return;
    const fetchPupil = async () => {
      try {
        const clean = ipRef.current.replace(/^https?:\/\//, '').split(':')[0];
        const res = await fetch(`http://${clean}:5005/darkest_point`);
        if (res.ok) {
          const data = await res.json();
          if (data.x_pct !== undefined && data.y_pct !== undefined) {
            setPupilPoint(data);
          }
        }
      } catch (e) { /* ignore */ }
    };
    const tid = setInterval(fetchPupil, 1000);
    return () => clearInterval(tid);
  }, [connected, ip]);

  const updateTranslation = useCallback(() => {
    if (!targetPoint || !pupilPoint || !imgContainerRef.current) {
      // Prevent infinite loop by not updating state if it's already 0
      setTranslate(prev => (prev.x === 0 && prev.y === 0) ? prev : { x: 0, y: 0 });
      return;
    }
    try {
      const cw = imgContainerRef.current.width;
      const ch = imgContainerRef.current.height;
      if (cw === 0 || ch === 0) return;
      
      const imgAspect = pupilPoint.width / pupilPoint.height;
      const viewAspect = cw / ch;
      let displayWidth, displayHeight;
      
      if (imgAspect > viewAspect) {
        displayWidth = cw;
        displayHeight = cw / imgAspect;
      } else {
        displayHeight = ch;
        displayWidth = ch * imgAspect;
      }
      
      const baseX = (cw - displayWidth) / 2 + pupilPoint.x_pct * displayWidth;
      const baseY = (ch - displayHeight) / 2 + pupilPoint.y_pct * displayHeight;
      
      const { zoomLevel, offsetX, offsetY } = zoomStateRef.current;
      let tx = (targetPoint.x - cw/2) / zoomLevel - baseX - offsetX + cw/2;
      let ty = (targetPoint.y - ch/2) / zoomLevel - baseY - offsetY + ch/2;
      
      const maxTx = cw * 0.4;
      const maxTy = ch * 0.4;
      tx = Math.max(-maxTx, Math.min(maxTx, tx));
      ty = Math.max(-maxTy, Math.min(maxTy, ty));
      
      setTranslate(prev => {
        if (Math.abs(prev.x - tx) < 0.1 && Math.abs(prev.y - ty) < 0.1) return prev;
        return { x: tx, y: ty };
      });
    } catch (e) { console.log('Align math error:', e); }
  }, [targetPoint, pupilPoint]);

  useEffect(() => {
    updateTranslation();
  }, [updateTranslation]);

  const handleZoomOrShift = useCallback((e, gestureState, zoomEvent) => {
    if (!zoomEvent) return;
    zoomStateRef.current = {
      zoomLevel: zoomEvent.zoomLevel,
      offsetX: zoomEvent.offsetX,
      offsetY: zoomEvent.offsetY,
    };
    updateTranslation();
  }, [updateTranslation]);

  const handleFocusTap = useCallback((event) => {
    const { locationX, locationY } = event.nativeEvent;
    setTargetPoint({ x: locationX, y: locationY });
    setFocusMode(false);
  }, []);

  const stop = () => { clearInterval(interval.current); interval.current = null; };
  const start = useCallback(() => {
    stop();
    interval.current = setInterval(async () => {
      const clean = ipRef.current.replace(/^https?:\/\//, '').split(':')[0];
      try {
        const c = new AbortController();
        const t = setTimeout(() => c.abort(), 2000);
        const r = await fetch(`http://${clean}:5005/status?t=${Date.now()}`, { signal: c.signal });
        clearTimeout(t);
        if (r.ok) {
          const d = await r.json();
          if (d.focus) setFocusMode(true);
          if (d.image_id !== lastId.current) {
            lastId.current = d.image_id;
            setImgUrl(`http://${clean}:5005/image?t=${Date.now()}`);
            setError(null);
          }
        }
      } catch (e) { if (e.name === 'AbortError') { setError('Timeout! PC Firewall block?'); } else { setError('Network error'); } }
    }, 500);
  }, []);

  const toggle = useCallback(() => {
    Keyboard.dismiss();
    if (connected) {
      stop(); 
      setConnected(false); 
      setImgUrl(null); 
      setError(null);
      setTargetPoint(null); // FIXED TypeError: Cannot set property 'current' of null
      setTranslate({ x: 0, y: 0 });
    } else { 
      start(); 
      setConnected(true); 
    }
  }, [connected, start]);

  useEffect(() => () => stop(), []);

  return (
    <View style={s.screen}>
      <View style={{ zIndex: 10, elevation: 10 }}>
        <IPHeader 
          ip={ip} 
          setIp={handleIpChange} 
          connected={connected} 
          onToggle={toggle} 
          focusMode={focusMode} 
          setFocusMode={setFocusMode}
          autoDiscover={autoDiscover} 
        />
      </View>
      {error && <View style={s.errBanner}><Text style={s.errText}>{error}</Text></View>}

      <View style={s.fill} onLayout={e => { imgContainerRef.current = e.nativeEvent.layout; }}>
        {imgUrl ? (
          <>
            <View style={[s.fill, { overflow: 'hidden' }]}>
              <ReactNativeZoomableView 
                maxZoom={100} minZoom={minZoom} initialZoom={1} bindToBorders={false} style={s.fill}
                onZoomAfter={handleZoomOrShift} onShiftingAfter={handleZoomOrShift}
              >
                <View style={[s.fill, { transform: [{ translateX: translate.x }, { translateY: translate.y }] }]}>
                  <Image source={{ uri: imgUrl }} style={s.fill} resizeMode="contain"
                    onError={e => setError(`Img: ${e.nativeEvent.error}`)} />
                </View>
              </ReactNativeZoomableView>
            </View>

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
              {connected ? '⏳ Waiting for feed…' : '📡 Enter PC IP and tap START'}
            </Text>
          </View>
        )}
      </View>
    </View>
  );
}

export default function App() {
  const [ip, setIp] = useState('192.168.1.3'); // PRE-FILLED WITH PC IP
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

const s = StyleSheet.create({
  root:   { flex: 1, backgroundColor: '#0A0A0A' },
  screen: { flex: 1, backgroundColor: '#0A0A0A' },
  fill:   { flex: 1 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  header: {
    flexDirection: 'row', padding: 8,
    backgroundColor: '#111122', alignItems: 'center',
    borderBottomWidth: 1, borderBottomColor: '#1E1E3F',
  },
  ipInputContainer: { 
    flex: 1, 
    marginRight: 8, 
    backgroundColor: '#16213E', 
    borderRadius: 8,
    paddingHorizontal: 8,
    justifyContent: 'center',
    height: 48,
    borderWidth: 1,
    borderColor: '#2A2A4A'
  },
  ipInputText: {
    color: '#00BCD4',
    fontSize: 22,
    fontWeight: 'bold',
  },
  controlsRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  smallBtn: {
    backgroundColor: '#2A2A4A',
    paddingHorizontal: 8,
    paddingVertical: 12,
    borderRadius: 6,
    marginLeft: 6,
    minWidth: 35,
    alignItems: 'center'
  },
  smallBtnActive: { backgroundColor: '#FF9800' },
  smallBtnStart:  { backgroundColor: '#00695C' },
  smallBtnStop:   { backgroundColor: '#B71C1C' },
  smallBtnText: {
    color: 'white',
    fontWeight: 'bold',
    fontSize: 12,
  },
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
});
