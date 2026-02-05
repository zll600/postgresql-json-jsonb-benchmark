-- MySQL initialization script for JSON benchmark
-- This script sets up the database with optimal settings for benchmarking

SELECT 'Initializing MySQL for JSON benchmark...' AS message;

-- Create database if not exists (with proper character set for JSON)
CREATE DATABASE IF NOT EXISTS json_benchmark_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

-- Ensure we're using the benchmark database
USE json_benchmark_db;

-- Grant privileges to benchmark user
GRANT ALL PRIVILEGES ON json_benchmark_db.* TO 'benchmark_user'@'%';
FLUSH PRIVILEGES;

-- Create a function to format bytes to human-readable size
DELIMITER //
CREATE FUNCTION IF NOT EXISTS format_bytes(bytes BIGINT)
RETURNS VARCHAR(20)
DETERMINISTIC
BEGIN
    IF bytes >= 1099511627776 THEN
        RETURN CONCAT(ROUND(bytes / 1099511627776, 2), ' TB');
    ELSEIF bytes >= 1073741824 THEN
        RETURN CONCAT(ROUND(bytes / 1073741824, 2), ' GB');
    ELSEIF bytes >= 1048576 THEN
        RETURN CONCAT(ROUND(bytes / 1048576, 2), ' MB');
    ELSEIF bytes >= 1024 THEN
        RETURN CONCAT(ROUND(bytes / 1024, 2), ' KB');
    ELSE
        RETURN CONCAT(bytes, ' B');
    END IF;
END//
DELIMITER ;
