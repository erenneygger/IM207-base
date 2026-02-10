
CREATE DATABASE IF NOT EXISTS parking_system;
USE parking_system;

CREATE TABLE tickets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plate_number VARCHAR(20),
    entry_time DATETIME,
    exit_time DATETIME
);

CREATE TABLE payments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ticket_id INT,
    amount DECIMAL(10,2),
    paid_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id)
);
