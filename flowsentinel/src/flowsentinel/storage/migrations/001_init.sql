-- Enable TimescaleDB extension if not already enabled
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- 1. Gas Prices Hypertable (tracks mempool gas prices over time)
CREATE TABLE IF NOT EXISTS gas_prices (
    time TIMESTAMPTZ NOT NULL,
    chain_id INTEGER NOT NULL,
    tx_hash VARCHAR(66) NOT NULL,
    gas_price DOUBLE PRECISION NOT NULL,
    target_address VARCHAR(42) NOT NULL,
    PRIMARY KEY (time, tx_hash, chain_id)
);

-- 2. Pool Depth Hypertable (tracks liquidity changes over time)
CREATE TABLE IF NOT EXISTS pool_depth (
    time TIMESTAMPTZ NOT NULL,
    pool_address VARCHAR(42) NOT NULL,
    exchange_name VARCHAR(50) NOT NULL,
    reserve0 DOUBLE PRECISION NOT NULL,
    reserve1 DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (time, pool_address)
);

-- 3. Orderbook Snapshots Hypertable (tracks spreads and book depth)
CREATE TABLE IF NOT EXISTS orderbook_snapshots (
    time TIMESTAMPTZ NOT NULL,
    pair VARCHAR(20) NOT NULL,
    mid_price DOUBLE PRECISION NOT NULL,
    spread DOUBLE PRECISION NOT NULL,
    bids JSONB NOT NULL,
    asks JSONB NOT NULL,
    PRIMARY KEY (time, pair)
);

-- Convert to TimescaleDB hypertables
SELECT create_hypertable('gas_prices', 'time', partitioning_column => 'chain_id', number_partitions => 4, if_not_exists => TRUE);
SELECT create_hypertable('pool_depth', 'time', if_not_exists => TRUE);
SELECT create_hypertable('orderbook_snapshots', 'time', if_not_exists => TRUE);

-- Create index for quick searches
CREATE INDEX IF NOT EXISTS idx_gas_prices_target ON gas_prices (target_address, time DESC);
CREATE INDEX IF NOT EXISTS idx_pool_depth_address ON pool_depth (pool_address, time DESC);
