-- Create booking system tables for Buddy Intelligence
-- Run with: psql -U surajpisal -d buddy_intelligence -p 6432 -f scripts/create_tables.sql

CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    full_name VARCHAR(255),
    phone VARCHAR(50),
    address TEXT,
    avatar_url TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS service_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    icon VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS services (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    base_price DECIMAL(10,2),
    duration_minutes INTEGER,
    category_id UUID REFERENCES service_categories(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    business_name VARCHAR(255) NOT NULL,
    description TEXT,
    email VARCHAR(255),
    phone VARCHAR(50),
    address TEXT,
    city VARCHAR(100),
    rating DECIMAL(3,2) DEFAULT 0,
    experience_years INTEGER DEFAULT 0,
    is_available BOOLEAN DEFAULT true,
    avatar_url TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bookings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_number VARCHAR(50) NOT NULL UNIQUE,
    user_id UUID NOT NULL REFERENCES "user"(id),
    service_id UUID REFERENCES services(id),
    provider_id UUID REFERENCES providers(id),
    service_date DATE NOT NULL,
    service_time VARCHAR(20) NOT NULL,
    location TEXT NOT NULL,
    special_instructions TEXT,
    status VARCHAR(50) DEFAULT 'awaiting_provider',
    estimated_price DECIMAL(10,2),
    final_price DECIMAL(10,2),
    provider_distance VARCHAR(50),
    estimated_arrival VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS booking_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id UUID NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    provider_id UUID NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'pending',
    score DECIMAL(5,2),
    notified_at TIMESTAMP,
    expires_at TIMESTAMP,
    responded_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS provider_services (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    service_id UUID NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Insert some sample service categories
INSERT INTO service_categories (id, name, description, icon) VALUES
    (gen_random_uuid(), 'Cleaning', 'Home and office cleaning services', 'spray'),
    (gen_random_uuid(), 'Plumbing', 'Plumbing repairs and installations', 'wrench'),
    (gen_random_uuid(), 'Electrical', 'Electrical repairs and installations', 'zap'),
    (gen_random_uuid(), 'Painting', 'Interior and exterior painting', 'paint-bucket')
ON CONFLICT DO NOTHING;
