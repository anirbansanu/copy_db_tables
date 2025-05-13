-- phpMyAdmin SQL Dump
-- version 4.9.5deb2
-- https://www.phpmyadmin.net/
--
-- Host: localhost:3306
-- Generation Time: May 12, 2025 at 07:59 PM
-- Server version: 8.0.42-0ubuntu0.20.04.1
-- PHP Version: 7.2.34-36+ubuntu20.04.1+deb.sury.org+1

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET AUTOCOMMIT = 0;
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `srihari_db_new`
--

-- --------------------------------------------------------

--
-- Table structure for table `inter_company_customers`
--

CREATE TABLE `inter_company_customers` (
  `id` int NOT NULL,
  `business_id` int NOT NULL,
  `contact_id` int NOT NULL COMMENT '" child company contact_id"',
  `parent_contact_id` int DEFAULT NULL COMMENT '"parent company contact_id"',
  `child_business_id` int DEFAULT NULL,
  `prefix` varchar(4) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` timestamp NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `inter_company_customers`
--

INSERT INTO `inter_company_customers` (`id`, `business_id`, `contact_id`, `parent_contact_id`, `child_business_id`, `prefix`, `created_at`, `updated_at`) VALUES
(1, 43, 10452, 10453, 44, NULL, '2025-05-03 02:28:33', '2025-05-02 20:58:33'),
(2, 43, 10457, 10453, 45, NULL, '2025-05-03 02:28:33', '2025-05-02 20:58:33'),
(3, 43, 10458, 10453, 46, NULL, '2025-05-03 02:28:33', '2025-05-02 20:58:33');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `inter_company_customers`
--
ALTER TABLE `inter_company_customers`
  ADD PRIMARY KEY (`id`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `inter_company_customers`
--
ALTER TABLE `inter_company_customers`
  MODIFY `id` int NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
