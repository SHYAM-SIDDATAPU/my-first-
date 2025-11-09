-- Users Table
CREATE TABLE users (
    name VARCHAR(100) PRIMARY KEY, 
    email VARCHAR(255) NOT NULL UNIQUE,
    threshold_value FLOAT DEFAULT 50.0 
);

-- Voiceprints Table
CREATE TABLE voiceprints (
    id INT AUTO_INCREMENT PRIMARY KEY, 
    user_name VARCHAR(100) NOT NULL, 
    voice_file VARCHAR(512) NOT NULL, 
    feature_file VARCHAR(512) NOT NULL,
    FOREIGN KEY (user_name) REFERENCES users(name) 
);