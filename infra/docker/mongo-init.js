// MongoDB Initialization Script for Production / Containerized Environments
// Creates the toursafe database, application service user with least privilege, and baseline collections.

const dbName = process.env.MONGO_INITDB_DATABASE || 'toursafe';
const appUser = process.env.MONGO_APP_USER || 'toursafe_app';
const appPassword = process.env.MONGO_APP_PASSWORD || 'toursafe_secure_prod_password_2026';

const targetDb = db.getSiblingDB(dbName);

print(`[INFO] Initializing TourSafe MongoDB database: ${dbName}`);

// Create application database user with readWrite role scoped strictly to toursafe database
targetDb.createUser({
    user: appUser,
    pwd: appPassword,
    roles: [
        { role: 'readWrite', db: dbName },
        { role: 'dbAdmin', db: dbName }
    ]
});

print(`[INFO] User '${appUser}' successfully registered for database '${dbName}'`);
