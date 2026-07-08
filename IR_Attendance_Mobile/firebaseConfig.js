import { initializeApp } from 'firebase/app';
import { getDatabase } from 'firebase/database';

// Firebase credentials matching the IR Attendance admin panel
const firebaseConfig = {
  databaseURL: "https://attendance-68878-default-rtdb.asia-southeast1.firebasedatabase.app/",
  // RTDB doesn't require complex config if we use REST or just the URL. 
  // However, since we are using api_secret in the Python app, we can authenticate requests manually or just pass it as a param.
  // The JS SDK doesn't natively support legacy database secrets for auth in the client SDK.
  // But wait, if the database rules allow read/write with a secret, we'll append it to REST calls 
  // or use the REST API manually for this simple app to avoid complex auth token minting.
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const database = getDatabase(app);

// We will export the database URL and Secret to do direct REST calls 
// which is exactly how the Python app does it.
export const DB_URL = firebaseConfig.databaseURL.replace(/\/$/, "");
export const API_SECRET = "apng5Iuu7ijd8QYZLTj9ZZ4UGsmYE6wLaenzhFRx";

export { database };
