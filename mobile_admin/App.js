
import React, { useState, useEffect, useRef } from 'react';
import { StyleSheet, View, Image, Alert, ScrollView, RefreshControl, Dimensions, Platform } from 'react-native';
import { Provider as PaperProvider, TextInput, Button, Text, DataTable, Appbar, ActivityIndicator, DefaultTheme, IconButton } from 'react-native-paper';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import * as Notifications from 'expo-notifications';
import { verifyPassword, listLicenses, activateLicense, revokeLicense, listRequests, deleteRequest } from './firebase_config';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

const theme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    primary: '#6200ee',
    accent: '#03dac4',
  },
};

export default function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const lastRequestCount = useRef(0);

  useEffect(() => {
    // Request notification permissions
    (async () => {
      const { status } = await Notifications.getPermissionsAsync();
      if (status !== 'granted') {
        await Notifications.requestPermissionsAsync();
      }
    })();

    // Poll for new requests every 30 seconds
    const interval = setInterval(async () => {
        try {
            const data = await listRequests();
            const currentCount = data ? Object.keys(data).length : 0;
            
            if (currentCount > lastRequestCount.current) {
                // New request found!
                await Notifications.scheduleNotificationAsync({
                    content: {
                        title: "New Activation Request",
                        body: "A user is waiting for approval.",
                        sound: true,
                    },
                    trigger: null,
                });
            }
            lastRequestCount.current = currentCount;
        } catch (e) {
            console.log("Polling error:", e);
        }
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  if (!isLoggedIn) {
    return (
      <PaperProvider theme={theme}>
        <SafeAreaProvider>
            <LoginScreen onLogin={() => setIsLoggedIn(true)} />
        </SafeAreaProvider>
      </PaperProvider>
    );
  }

  return (
    <PaperProvider theme={theme}>
        <SafeAreaProvider>
            <DashboardScreen onLogout={() => setIsLoggedIn(false)} />
        </SafeAreaProvider>
    </PaperProvider>
  );
}

import * as LocalAuthentication from 'expo-local-authentication';

function LoginScreen({ onLogin }) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isBiometricSupported, setIsBiometricSupported] = useState(false);

  useEffect(() => {
    (async () => {
      const compatible = await LocalAuthentication.hasHardwareAsync();
      setIsBiometricSupported(compatible);
    })();
  }, []);

  const handleLogin = () => {
    if (verifyPassword(password)) {
      onLogin();
    } else {
      setError("Incorrect Password");
    }
  };

  const handleBiometricLogin = async () => {
    try {
      const savedBiometrics = await LocalAuthentication.isEnrolledAsync();
      if (!savedBiometrics) {
        Alert.alert("Biometric Record Not Found", "Please verify your text record", [{ text: "OK" }]);
        return;
      }

      const result = await LocalAuthentication.authenticateAsync({
        promptMessage: 'Login with Biometrics',
        fallbackLabel: 'Use Password',
      });

      if (result.success) {
        onLogin();
      } else {
        setError("Biometric authentication failed");
      }
    } catch (e) {
      console.log(e);
      setError("Biometric error");
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.content}>
        <Image 
            source={require('./assets/icon.png')} 
            style={{ width: 100, height: 100, alignSelf: 'center', marginBottom: 20 }}
            resizeMode="contain"
        />
        <Text variant="headlineMedium" style={{ textAlign: 'center', marginBottom: 20 }}>IRIS Activation</Text>
        <TextInput
          label="Admin Password"
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          mode="outlined"
          style={{ marginBottom: 10 }}
        />
        {error ? <Text style={{ color: 'red', marginBottom: 10 }}>{error}</Text> : null}
        
        <Button mode="contained" onPress={handleLogin} style={{ marginTop: 10 }}>
          Login
        </Button>

        {isBiometricSupported && (
            <Button 
                mode="outlined" 
                onPress={handleBiometricLogin} 
                style={{ marginTop: 20 }}
                icon="fingerprint"
            >
                Login with Fingerprint/FaceID
            </Button>
        )}
      </View>
    </SafeAreaView>
  );
}

function DashboardScreen({ onLogout }) {
  const [activeTab, setActiveTab] = useState('generate'); // 'generate', 'manage', 'mirror'

  return (
    <View style={{ flex: 1, backgroundColor: '#f5f5f5' }}>
        <Appbar.Header elevated>
            <Appbar.Content title="Admin Dashboard" />
            <Appbar.Action icon="logout" onPress={onLogout} />
        </Appbar.Header>
        
        <View style={styles.tabContainer}>
            <Button 
                mode={activeTab === 'requests' ? 'contained' : 'text'} 
                onPress={() => setActiveTab('requests')}
                style={styles.tabButton}
                shape={{ borderRadius: 0 }}
                labelStyle={{ fontSize: 12 }}
            >
                Requests
            </Button>
            <Button 
                mode={activeTab === 'generate' ? 'contained' : 'text'} 
                onPress={() => setActiveTab('generate')}
                style={styles.tabButton}
                shape={{ borderRadius: 0 }}
                labelStyle={{ fontSize: 12 }}
            >
                Generate
            </Button>
            <Button 
                mode={activeTab === 'manage' ? 'contained' : 'text'} 
                onPress={() => setActiveTab('manage')}
                style={styles.tabButton}
                shape={{ borderRadius: 0 }}
                labelStyle={{ fontSize: 12 }}
            >
                Users
            </Button>
        </View>
        <View style={{ flex: 1 }}>
            {activeTab === 'requests' ? <RequestsTab /> : (activeTab === 'generate' ? <GenerateTab /> : <ManageUsersTab />)}
        </View>
    </View>
  );
}

function RequestsTab() {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const loadRequests = async () => {
    setLoading(true);
    const data = await listRequests();
    if (data) {
        const reqList = Object.keys(data).map(key => ({
            id: key,
            ...data[key]
        }));
        setRequests(reqList);
    } else {
        setRequests([]);
    }
    setLoading(false);
  };

  const onRefresh = async () => {
      setRefreshing(true);
      await loadRequests();
      setRefreshing(false);
  };

  useEffect(() => {
    loadRequests();
  }, []);

  const handleApprove = async (mid, username) => {
    setLoading(true);
    // 1. Activate
    const res = await activateLicense(mid, username);
    if (res.success) {
        // 2. Delete request
        await deleteRequest(mid);
        Alert.alert("Success", `Activated user: ${username}`);
        loadRequests();
    } else {
        Alert.alert("Error", res.message);
        setLoading(false);
    }
  };

  const handleReject = async (mid) => {
    Alert.alert(
        "Reject Request",
        "Are you sure you want to delete this request?",
        [
            { text: "Cancel", style: "cancel" },
            { 
                text: "Delete", 
                style: 'destructive',
                onPress: async () => {
                    setLoading(true);
                    await deleteRequest(mid);
                    loadRequests();
                }
            }
        ]
    );
  };

  return (
    <View style={{ flex: 1 }}>
        <View style={styles.headerRow}>
            <Text variant="titleMedium">Pending Requests</Text>
            <Button icon="refresh" onPress={loadRequests} compact>Refresh</Button>
        </View>

        {loading && !refreshing ? <ActivityIndicator animating={true} style={{ marginTop: 20 }} /> : (
            <ScrollView 
                contentContainerStyle={{ flexGrow: 1 }}
                refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
            >
                {requests.length === 0 ? (
                    <Text style={{ textAlign: 'center', marginTop: 40, color: '#888' }}>No pending requests</Text>
                ) : (
                    requests.map((item) => (
                        <View key={item.id} style={styles.requestCard}>
                            <View style={{ flex: 1 }}>
                                <Text style={{ fontWeight: 'bold', fontSize: 16 }}>{item.username}</Text>
                                <Text style={{ color: '#666', fontSize: 12 }}>ID: {item.id}</Text>
                                <Text style={{ color: '#888', fontSize: 11 }}>{item.timestamp}</Text>
                            </View>
                            <View style={{ flexDirection: 'row' }}>
                                <IconButton icon="check-circle" iconColor="green" size={28} onPress={() => handleApprove(item.id, item.username)} />
                                <IconButton icon="close-circle" iconColor="red" size={28} onPress={() => handleReject(item.id)} />
                            </View>
                        </View>
                    ))
                )}
            </ScrollView>
        )}
    </View>
  );
}

function GenerateTab() {
  const [username, setUsername] = useState('');
  const [requestCode, setRequestCode] = useState('');
  const [result, setResult] = useState('');
  const [loading, setLoading] = useState(false);

  const handleGenerate = async () => {
    if (!username || !requestCode) {
      Alert.alert("Error", "Please fill all fields");
      return;
    }

    setLoading(true);
    const response = await activateLicense(requestCode, username);
    setLoading(false);

    if (response.success) {
      setResult(response.code);
      Alert.alert("Success", `Activation Code: ${response.code}`);
    } else {
      Alert.alert("Error", response.message);
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.content}>
      <Text variant="titleMedium" style={{ marginBottom: 15 }}>Generate Activation Code</Text>
      
      <TextInput
        label="Username (Client)"
        value={username}
        onChangeText={setUsername}
        mode="outlined"
        style={{ marginBottom: 10, backgroundColor: 'white' }}
      />
      
      <TextInput
        label="Request Code"
        value={requestCode}
        onChangeText={setRequestCode}
        mode="outlined"
        multiline
        numberOfLines={3}
        style={{ marginBottom: 20, backgroundColor: 'white' }}
      />
      
      <Button mode="contained" onPress={handleGenerate} loading={loading} disabled={loading} contentStyle={{ height: 50 }}>
        Generate & Activate
      </Button>

      {result ? (
        <View style={styles.resultContainer}>
            <Text style={{ textAlign: 'center', color: '#555' }}>Activation Code:</Text>
            <Text variant="headlineSmall" style={{ textAlign: 'center', fontWeight: 'bold', marginTop: 5, color: '#6200ee' }}>{result}</Text>
        </View>
      ) : null}
    </ScrollView>
  );
}

function ManageUsersTab() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const loadUsers = async () => {
    setLoading(true);
    const data = await listLicenses();
    if (data) {
        const userList = Object.keys(data).map(key => ({
            id: key,
            ...data[key]
        }));
        setUsers(userList);
    }
    setLoading(false);
  };

  const onRefresh = async () => {
      setRefreshing(true);
      await loadUsers();
      setRefreshing(false);
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const handleRevoke = async (id) => {
    Alert.alert(
        "Confirm Revoke",
        `Are you sure you want to revoke license for ${id}?`,
        [
            { text: "Cancel", style: "cancel" },
            { 
                text: "Revoke", 
                style: 'destructive',
                onPress: async () => {
                    setLoading(true);
                    const res = await revokeLicense(id);
                    if (res.success) {
                        Alert.alert("Success", "License Revoked");
                        loadUsers();
                    } else {
                        Alert.alert("Error", res.message);
                        setLoading(false);
                    }
                }
            }
        ]
    );
  };

  return (
    <View style={{ flex: 1 }}>
        <View style={styles.headerRow}>
            <Text variant="titleMedium">Registered Users ({users.length})</Text>
            <Button icon="refresh" onPress={loadUsers} compact>Refresh</Button>
        </View>

        {loading && !refreshing ? <ActivityIndicator animating={true} style={{ marginTop: 20 }} /> : (
            <ScrollView 
                contentContainerStyle={{ flexGrow: 1 }}
                refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
            >
                <DataTable>
                    <DataTable.Header>
                        <DataTable.Title>User</DataTable.Title>
                        <DataTable.Title>ID</DataTable.Title>
                        <DataTable.Title numeric>Action</DataTable.Title>
                    </DataTable.Header>

                    {users.map((item) => (
                        <DataTable.Row key={item.id}>
                            <DataTable.Cell>
                                <View>
                                    <Text style={{ fontWeight: 'bold' }}>{item.username}</Text>
                                    <Text style={{ fontSize: 10, color: 'green' }}>{item.status}</Text>
                                </View>
                            </DataTable.Cell>
                            <DataTable.Cell>
                                <Text style={{ fontSize: 10 }}>{item.id.substring(0, 15)}...</Text>
                            </DataTable.Cell>
                            <DataTable.Cell numeric>
                                <Button mode="text" textColor="red" compact onPress={() => handleRevoke(item.id)}>Revoke</Button>
                            </DataTable.Cell>
                        </DataTable.Row>
                    ))}
                </DataTable>
            </ScrollView>
        )}
    </View>
  );
}



const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
    justifyContent: 'center',
  },
  content: {
    padding: 20,
  },
  tabContainer: {
      flexDirection: 'row',
      backgroundColor: '#fff',
      elevation: 2,
  },
  tabButton: {
      flex: 1,
      borderRadius: 0,
  },
  resultContainer: {
      marginTop: 30, 
      padding: 20, 
      backgroundColor: '#ede7f6', 
      borderRadius: 8,
      borderWidth: 1,
      borderColor: '#d1c4e9'
  },
  headerRow: {
      flexDirection: 'row', 
      justifyContent: 'space-between', 
      alignItems: 'center', 
      paddingHorizontal: 15,
      paddingVertical: 10,
      backgroundColor: '#fff'
  },
  requestCard: {
      flexDirection: 'row',
      alignItems: 'center',
      backgroundColor: '#fff',
      padding: 15,
      marginHorizontal: 10,
      marginVertical: 5,
      borderRadius: 8,
      elevation: 1,
  }
});
