import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  StyleSheet, Text, View, TextInput, TouchableOpacity,
  ActivityIndicator, Alert, ScrollView, Pressable, FlatList, Modal, Vibration
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { DB_URL, API_SECRET, database } from './firebaseConfig';
import { ref, onValue, set } from 'firebase/database';
import { Audio } from 'expo-av';

export default function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [userName, setUserName] = useState('');
  const [userPin, setUserPin] = useState('');
  const pinInputRef = useRef(null);
  const [activeScreen, setActiveScreen] = useState('home');

  const [currentTime, setCurrentTime] = useState('');
  const [batchData, setBatchData] = useState(null);
  const [folders, setFolders] = useState([]);
  const [isAppRunning, setIsAppRunning] = useState(false);
  const [brightnessVal, setBrightnessVal] = useState('');
  const [isBatchModalVisible, setIsBatchModalVisible] = useState(false);
  const flatListRef = useRef(null);

  // Refs for internal state that shouldn't re-trigger effects
  const soundRef = useRef(null);
  const didCompleteSoundRef = useRef(false); // prevent repeated alarm
  const brightDebounceRef = useRef(null);
  const userPinRef = useRef('');
  const isMountedRef = useRef(true);

  // Keep ref in sync with state
  useEffect(() => { userPinRef.current = userPin; }, [userPin]);

  // Clock
  useEffect(() => {
    const timer = setInterval(() => {
      const now = new Date();
      setCurrentTime(now.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true }));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => { isMountedRef.current = false; };
  }, []);

  // Configure audio session on mount
  useEffect(() => {
    Audio.setAudioModeAsync({
      allowsRecordingIOS: false,
      staysActiveInBackground: true,
      playsInSilentModeIOS: true,
      shouldDuckAndroid: false,
      playThroughEarpieceAndroid: false,
    });
  }, []);

  // Real-time Firebase database listener
  useEffect(() => {
    if (!isLoggedIn || !userPin) return;

    const pin = userPin;
    const sessionRef = ref(database, `sessions/${pin}`);

    const unsubscribe = onValue(sessionRef, (snapshot) => {
      if (!isMountedRef.current) return;
      const data = snapshot.val();
      if (data) {
        setBatchData(prev => {
          if (JSON.stringify(prev) === JSON.stringify(data)) return prev;
          return data;
        });

        if (data.folders) {
          setFolders(data.folders);
        }

        if (data.timestamp) {
          const now = Date.now() / 1000;
          setIsAppRunning(now - data.timestamp < 15);
          if (now - data.timestamp < 15 && data.global_default_brightness !== undefined) {
            setBrightnessVal(v => {
              const newVal = String(data.global_default_brightness);
              return v !== newVal ? newVal : v;
            });
          }
        }

        // Completion alarm: all done
        if (
          data.stats &&
          data.stats.total > 0 &&
          data.stats.total === (data.stats.success + data.stats.fail + data.stats.skip)
        ) {
          playCompletionSound();
        } else if (data.stats && data.stats.success === 0 && data.stats.fail === 0) {
          // Reset alarm flag when a new batch starts
          didCompleteSoundRef.current = false;
        }
      } else {
        setIsAppRunning(false);
      }
    }, (error) => {
      console.log('Firebase subscription error:', error);
    });

    return () => {
      unsubscribe();
    };
  }, [isLoggedIn, userPin]);

  const checkLoginStatus = async () => {
    try {
      const savedPin = await AsyncStorage.getItem('userPin');
      const savedName = await AsyncStorage.getItem('userName');
      if (savedPin && savedName) {
        setUserPin(savedPin);
        setUserName(savedName);
        setIsLoggedIn(true);
      }
    } catch (e) { console.error(e); }
    setIsLoading(false);
  };

  useEffect(() => { checkLoginStatus(); }, []);

  const handleLogin = async (pinStr) => {
    if (pinStr.length !== 6) return;
    setIsLoading(true);
    try {
      const response = await fetch(`${DB_URL}/licenses.json?auth=${API_SECRET}`);
      const data = await response.json();
      let valid = false;
      if (data) {
        for (const key in data) {
          const user = data[key];
          if (String(user.activation_code) === pinStr && user.status === 'active') {
            valid = true;
            setUserName(user.username || 'User');
            await AsyncStorage.setItem('userPin', pinStr);
            await AsyncStorage.setItem('userName', user.username || 'User');
            break;
          }
        }
      }
      if (valid) { setIsLoggedIn(true); }
      else { Alert.alert('Login Failed', 'Invalid PIN or Account is inactive.'); }
    } catch (e) { Alert.alert('Error', 'Network error connecting to Firebase.'); }
    setIsLoading(false);
  };

  const handleLogout = async () => {
    await AsyncStorage.removeItem('userPin');
    await AsyncStorage.removeItem('userName');
    setIsLoggedIn(false);
    setUserPin('');
    setBatchData(null);
    didCompleteSoundRef.current = false;
  };

  const playCompletionSound = async () => {
    if (didCompleteSoundRef.current) return; // already played
    didCompleteSoundRef.current = true;

    const stopSound = async () => {
      if (soundRef.current) {
        try {
          await soundRef.current.stopAsync();
          await soundRef.current.unloadAsync();
        } catch (err) {
          console.log('Error stopping sound:', err);
        }
        soundRef.current = null;
      }
    };

    try {
      // Vibrate strongly 3 times
      Vibration.vibrate([0, 500, 200, 500, 200, 500]);

      // Play the samsung washing sound from assets
      if (soundRef.current) {
        await soundRef.current.unloadAsync();
        soundRef.current = null;
      }
      const { sound } = await Audio.Sound.createAsync(
        require('./assets/samsung_washing.mp3'),
        { shouldPlay: true, volume: 1.0 }
      );
      soundRef.current = sound;
      sound.setOnPlaybackStatusUpdate((status) => {
        if (status.didJustFinish) {
          sound.unloadAsync();
          soundRef.current = null;
        }
      });

      // Show alert
      Alert.alert(
        '✅ Attendance Complete!',
        'All students have been processed successfully!',
        [{ text: 'OK', onPress: stopSound }]
      );
    } catch (e) {
      console.log('Sound playback error:', e);
      // Still show alert even if sound fails
      Alert.alert(
        '✅ Attendance Complete!',
        'All students have been processed successfully!',
        [{ text: 'OK', onPress: stopSound }]
      );
    }
  };

  const sendCommand = async (actionStr, payload = {}) => {
    const pin = userPinRef.current;
    if (!pin) return;
    const finalPayload = { action: actionStr, ...payload, t: Date.now() };
    try {
      // Use Firebase native WebSocket set (sub-30ms propagation)
      await set(ref(database, `sessions/${pin}/command`), finalPayload);
    } catch (e) {
      console.log('Command via WebSocket set failed, trying REST fallback:', e);
      try {
        await fetch(`${DB_URL}/sessions/${pin}/command.json?auth=${API_SECRET}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(finalPayload)
        });
      } catch (err) {
        console.log('Fallback command failed:', err);
      }
    }
  };

  const handleBrightnessChange = (val) => {
    setBrightnessVal(val);
    clearTimeout(brightDebounceRef.current);
    brightDebounceRef.current = setTimeout(() => {
      sendCommand('set_brightness', { value: val });
    }, 400);
  };

  const renderFolderItem = ({ item }) => {
    let textColor = '#111';
    if (item.status === 'success') textColor = '#2E7D32';
    if (item.status === 'fail') textColor = '#C62828';
    if (item.status === 'skip') textColor = '#9E9E9E';

    const isActive = batchData?.current_folder === item.name;

    return (
      <View style={[
        styles.listItem,
        isActive && styles.listItemActive,
      ]}>
        <Text style={[styles.listItemText, { color: textColor }, isActive && styles.listItemTextActive]}>
          {item.name}
        </Text>
      </View>
    );
  };

  // Auto-scroll to active item
  useEffect(() => {
    if (batchData?.current_folder && flatListRef.current && folders.length > 0) {
      const index = folders.findIndex(f => f.name === batchData.current_folder);
      if (index >= 0) {
        flatListRef.current.scrollToIndex({ index, animated: true, viewPosition: 0.5 });
      }
    }
  }, [batchData?.current_folder]);

  if (isLoading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#00D4FF" />
      </View>
    );
  }

  if (!isLoggedIn) {
    return (
      <View style={styles.center}>
        <Text style={styles.title}>IR Attendance</Text>
        <Text style={styles.subtitle}>Enter your 6-digit PIN</Text>
        <Pressable style={styles.otpContainer} onPress={() => pinInputRef.current?.focus()}>
          {[0, 1, 2, 3, 4, 5].map((index) => (
            <View key={index} style={[styles.otpBox, userPin.length === index && styles.otpBoxActive]}>
              <Text style={styles.otpText}>{userPin[index] || ''}</Text>
            </View>
          ))}
        </Pressable>
        <TextInput
          ref={pinInputRef}
          style={styles.hiddenInput}
          value={userPin}
          onChangeText={(text) => {
            const clean = text.replace(/[^0-9]/g, '');
            setUserPin(clean);
            if (clean.length === 6) handleLogin(clean);
          }}
          keyboardType="numeric"
          maxLength={6}
          autoFocus={true}
          caretHidden={true}
        />
      </View>
    );
  }

  const TopBar = () => (
    <View style={styles.topBar}>
      <View style={{ flexDirection: 'row', alignItems: 'center' }}>
        {activeScreen === 'attendance' && (
          <TouchableOpacity onPress={() => setActiveScreen('home')} style={{ marginRight: 15 }}>
            <Text style={{ fontSize: 24, fontWeight: 'bold', color: '#333' }}>←</Text>
          </TouchableOpacity>
        )}
        <Text style={styles.greeting}>Hi, {userName}</Text>
      </View>
      <Text style={styles.time}>{currentTime}</Text>
    </View>
  );

  if (activeScreen === 'home') {
    return (
      <View style={styles.container}>
        <TopBar />
        <View style={[styles.center, { paddingHorizontal: 20 }]}>
          <TouchableOpacity style={[styles.largeButton, { backgroundColor: '#FF9800' }]} onPress={async () => {
            try {
              // Use WebSocket set
              await set(ref(database, 'service_commands/command'), 'start_apps');
              Alert.alert('Sent', 'Command sent to PC to launch apps!');
            } catch (e) {
              console.log('Launch command via WebSocket failed, trying fallback:', e);
              try {
                await fetch(`${DB_URL}/service_commands/command.json?auth=${API_SECRET}`, {
                  method: 'PUT',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify('start_apps')
                });
                Alert.alert('Sent', 'Command sent to PC to launch apps!');
              } catch (err) {
                Alert.alert('Error', 'Failed to send command.');
              }
            }
          }}>
            <Text style={styles.largeButtonText}>🚀 Launch Apps on PC</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.largeButton, { backgroundColor: '#00D4FF', marginTop: 20 }]}
            onPress={() => setActiveScreen('attendance')}
          >
            <Text style={styles.largeButtonText}>📊 Computer Attendance</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.button, { backgroundColor: '#333', marginTop: 60, width: '50%' }]}
            onPress={handleLogout}
          >
            <Text style={styles.buttonText}>Logout</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <TopBar />

      <View style={styles.contentArea}>
        {batchData ? (
          <View style={styles.liveView}>

            {/* Batch Selector */}
            <TouchableOpacity style={styles.batchSelector} onPress={() => setIsBatchModalVisible(true)}>
              <Text style={styles.batchTitle}>📁 {batchData.batch_name || 'Select Batch'}</Text>
              <Text style={{ fontSize: 18 }}>▼</Text>
            </TouchableOpacity>

            {/* Stats Bar */}
            <View style={styles.statsBar}>
              <Text style={styles.statItem}>Total: {batchData.stats?.total || 0}</Text>
              <Text style={[styles.statItem, { color: '#2E7D32' }]}>✅ {batchData.stats?.success || 0}</Text>
              <Text style={[styles.statItem, { color: '#C62828' }]}>❌ {batchData.stats?.fail || 0}</Text>
              <Text style={[styles.statItem, { color: '#9E9E9E' }]}>✂️ {batchData.stats?.skip || 0}</Text>
            </View>

            {/* Folder List */}
            <View style={styles.listContainer}>
              <FlatList
                ref={flatListRef}
                data={folders}
                renderItem={renderFolderItem}
                keyExtractor={(item) => item.name}
                showsVerticalScrollIndicator={true}
                onScrollToIndexFailed={(info) => {
                  setTimeout(() => {
                    flatListRef.current?.scrollToIndex({ index: info.index, animated: true });
                  }, 500);
                }}
              />
            </View>
          </View>
        ) : (
          <View style={styles.card}>
            <Text style={styles.subtitle}>Waiting for PC data...</Text>
            <ActivityIndicator size="small" color="#00D4FF" style={{ marginTop: 10 }} />
          </View>
        )}
      </View>

      {/* Footer Controls */}
      <View style={styles.footerControls}>
        <View style={styles.brightnessRow}>
          <Text style={{ fontWeight: 'bold', fontSize: 14, color: '#555' }}>Default Brightness</Text>
          <TextInput
            style={styles.brightnessInput}
            keyboardType="numeric"
            value={brightnessVal}
            onChangeText={handleBrightnessChange}
            placeholder="100"
          />
        </View>

        <TouchableOpacity
          style={[styles.startStopBtn, { backgroundColor: batchData?.is_auto_running ? '#C62828' : '#2E7D32' }]}
          onPress={() => sendCommand(batchData?.is_auto_running ? 'stop' : 'start')}
        >
          <Text style={styles.buttonText}>
            {batchData?.is_auto_running ? '⏹ STOP ATTENDANCE' : '▶ START ATTENDANCE'}
          </Text>
        </TouchableOpacity>
      </View>

      {/* Batch Selection Modal */}
      <Modal visible={isBatchModalVisible} animationType="slide" transparent={true}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Select Batch</Text>
            <ScrollView style={{ maxHeight: 400, width: '100%' }}>
              {batchData?.available_batches?.length > 0 ? batchData.available_batches.map((batch, idx) => (
                <TouchableOpacity
                  key={idx}
                  style={styles.modalItem}
                  onPress={() => {
                    sendCommand('load_batch', { batch_name: batch });
                    setIsBatchModalVisible(false);
                  }}
                >
                  <Text style={{ fontSize: 16, color: '#333' }}>{batch}</Text>
                </TouchableOpacity>
              )) : (
                <Text style={{ textAlign: 'center', margin: 20, color: '#999' }}>No batches available.</Text>
              )}
            </ScrollView>
            <TouchableOpacity style={styles.modalCancel} onPress={() => setIsBatchModalVisible(false)}>
              <Text style={{ color: 'white', fontWeight: 'bold' }}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#121212' },
  container: { flex: 1, backgroundColor: '#f0f2f5', paddingTop: 50 },
  topBar: {
    flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: 20,
    paddingVertical: 15, backgroundColor: '#fff', borderBottomWidth: 1, borderBottomColor: '#e5e5e5',
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.08, shadowRadius: 3, elevation: 2
  },
  greeting: { fontSize: 20, fontWeight: 'bold', color: '#333' },
  time: { fontSize: 18, color: '#666' },
  title: { fontSize: 32, fontWeight: 'bold', textAlign: 'center', color: '#00D4FF' },
  subtitle: { fontSize: 16, textAlign: 'center', color: '#888', marginBottom: 30 },
  card: { backgroundColor: '#fff', padding: 20, margin: 20, borderRadius: 12, elevation: 2 },
  button: { backgroundColor: '#00D4FF', paddingVertical: 15, borderRadius: 8, alignItems: 'center' },
  largeButton: {
    width: '100%', paddingVertical: 30, borderRadius: 15, alignItems: 'center',
    shadowColor: '#000', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.2, shadowRadius: 6, elevation: 6
  },
  largeButtonText: { color: '#fff', fontSize: 20, fontWeight: 'bold' },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: 'bold' },
  contentArea: { flex: 1 },
  liveView: { margin: 12, flex: 1 },
  batchSelector: {
    flexDirection: 'row', justifyContent: 'space-between', backgroundColor: '#fff',
    padding: 15, borderRadius: 12, marginBottom: 8, borderWidth: 1, borderColor: '#e0e0e0',
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.06, shadowRadius: 2, elevation: 1
  },
  batchTitle: { fontSize: 16, fontWeight: 'bold', color: '#333' },
  statsBar: {
    flexDirection: 'row', justifyContent: 'space-between', backgroundColor: '#fff',
    paddingHorizontal: 15, paddingVertical: 12, borderRadius: 12, marginBottom: 8,
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.06, shadowRadius: 2, elevation: 1
  },
  statItem: { fontSize: 14, fontWeight: 'bold', color: '#555' },
  listContainer: { flex: 1, backgroundColor: '#f0f2f5' },

  // List items - clean white cards
  listItem: {
    backgroundColor: '#fff',
    borderRadius: 12,
    marginVertical: 4,
    marginHorizontal: 4,
    paddingVertical: 18,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: '#fff',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 2,
    elevation: 1,
  },
  listItemActive: {
    borderColor: '#00D4FF',
    shadowColor: '#00D4FF',
    shadowOpacity: 0.25,
    shadowRadius: 6,
    elevation: 4,
  },
  listItemText: { fontSize: 22, fontWeight: '600', textAlign: 'center' },
  listItemTextActive: { fontWeight: 'bold', fontSize: 24 },

  footerControls: {
    padding: 16, backgroundColor: '#fff', borderTopWidth: 1, borderTopColor: '#e5e5e5',
    shadowColor: '#000', shadowOffset: { width: 0, height: -1 }, shadowOpacity: 0.05, shadowRadius: 3, elevation: 3
  },
  brightnessRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  brightnessInput: {
    borderWidth: 1, borderColor: '#ddd', borderRadius: 8, padding: 8,
    width: 80, textAlign: 'center', fontSize: 16, backgroundColor: '#f9f9f9'
  },
  startStopBtn: { paddingVertical: 18, borderRadius: 12, alignItems: 'center' },

  // Login
  otpContainer: { flexDirection: 'row', justifyContent: 'space-between', width: '80%', marginVertical: 20 },
  otpBox: {
    width: 45, height: 55, borderWidth: 2, borderColor: '#444', borderRadius: 10,
    justifyContent: 'center', alignItems: 'center', backgroundColor: '#1e1e1e'
  },
  otpBoxActive: { borderColor: '#00D4FF' },
  otpText: { fontSize: 24, fontWeight: 'bold', color: '#fff' },
  hiddenInput: { position: 'absolute', width: 1, height: 1, opacity: 0 },

  // Modal
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'flex-end' },
  modalContent: {
    backgroundColor: '#fff', padding: 20,
    borderTopLeftRadius: 24, borderTopRightRadius: 24, alignItems: 'center',
    shadowColor: '#000', shadowOffset: { width: 0, height: -3 }, shadowOpacity: 0.15, shadowRadius: 10, elevation: 10
  },
  modalTitle: { fontSize: 20, fontWeight: 'bold', marginBottom: 15, color: '#333' },
  modalItem: { paddingVertical: 16, width: '100%', borderBottomWidth: 1, borderBottomColor: '#f0f0f0', alignItems: 'center' },
  modalCancel: { marginTop: 16, backgroundColor: '#C62828', paddingVertical: 14, paddingHorizontal: 50, borderRadius: 12 }
});
