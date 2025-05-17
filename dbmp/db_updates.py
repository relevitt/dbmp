updates = {
    0: """
    -- Step 1: Create new spotify_auth_clients table
    CREATE TABLE IF NOT EXISTS spotify_auth_clients (
        client_id TEXT NOT NULL,
        user_id TEXT NOT NULL
    );

    -- Step 2: Populate it from existing spotify_auth
    INSERT INTO spotify_auth_clients (client_id, user_id)
    SELECT client_id, user_id FROM spotify_auth;

    -- Step 3: Create a new spotify_auth_temp table without client_id
    CREATE TABLE spotify_auth_new (
        user_id TEXT NOT NULL,
        access_token TEXT NOT NULL,
        expires_in INTEGER NOT NULL,
        refresh_token TEXT NOT NULL
    );

    -- Step 4: Copy data into the new table
    INSERT INTO spotify_auth_new (user_id, access_token, expires_in, refresh_token)
    SELECT user_id, access_token, expires_in, refresh_token FROM spotify_auth;

    -- Step 5: Drop the old table and rename the new one
    DROP TABLE spotify_auth;
    ALTER TABLE spotify_auth_new RENAME TO spotify_auth;
    """
}
