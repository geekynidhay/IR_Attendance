
// firebase_config.js
// Replicates logic from license_manager.py

const DATABASE_URL = "https://attendance-68878-default-rtdb.asia-southeast1.firebasedatabase.app/";
const API_SECRET = "apng5Iuu7ijd8QYZLTj9ZZ4UGsmYE6wLaenzhFRx"; // Database Secret

export const verifyPassword = (inputPassword) => {
    return inputPassword === "Nidhay@2003";
};

export const listLicenses = async () => {
    try {
        const url = `${DATABASE_URL}/licenses.json?auth=${API_SECRET}`;
        const response = await fetch(url);
        if (!response.ok) throw new Error("Network response was not ok");
        const data = await response.json();
        return data || {};
    } catch (error) {
        console.error("Error fetching licenses:", error);
        return {};
    }
};

export const activateLicense = async (request_code, username) => {
    try {
        // Request code format: MachineID|... or just MachineID
        const parts = request_code.split('|');
        const machine_id = parts[0];

        // Generate a 6-digit PIN for Mobile App authentication
        const activation_code = String(Math.floor(100000 + Math.random() * 900000));

        // Generate a 32-byte base64url-encoded encryption key (compatible with Fernet)
        const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
        let encryption_key = '';
        for (let i = 0; i < 44; i++) {
            encryption_key += chars.charAt(Math.floor(Math.random() * chars.length));
        }

        const data = {
            username: username,
            status: "active",
            last_seen: "never",
            activation_code: activation_code,
            encryption_key: encryption_key
        };

        const url = `${DATABASE_URL}/licenses/${machine_id}.json?auth=${API_SECRET}`;
        const response = await fetch(url, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });

        if (response.ok) {
            return { success: true, code: activation_code };
        } else {
            const errorText = await response.text();
            return { success: false, message: errorText };
        }

    } catch (error) {
        return { success: false, message: error.toString() };
    }
};

export const revokeLicense = async (machine_id) => {
    try {
        const url = `${DATABASE_URL}/licenses/${machine_id}.json?auth=${API_SECRET}`;
        const response = await fetch(url, {
            method: 'DELETE'
        });
        return { success: response.ok };
    } catch (error) {
        return { success: false, message: error.toString() };
    }
};

export const listRequests = async () => {
    try {
        const url = `${DATABASE_URL}/activation_requests.json?auth=${API_SECRET}`;
        const response = await fetch(url);
        if (!response.ok) throw new Error("Network response was not ok");
        const data = await response.json();
        return data || {};
    } catch (error) {
        console.error("Error fetching requests:", error);
        return {};
    }
};

export const deleteRequest = async (machine_id) => {
    try {
        const url = `${DATABASE_URL}/activation_requests/${machine_id}.json?auth=${API_SECRET}`;
        const response = await fetch(url, {
            method: 'DELETE'
        });
        return response.ok;
    } catch (error) {
        console.error("Error deleting request:", error);
        return false;
    }
};
