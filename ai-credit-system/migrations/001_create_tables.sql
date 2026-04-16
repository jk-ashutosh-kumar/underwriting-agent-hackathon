-- Ingestion Agent: Database Schema + Seed Data
-- Run this in Supabase SQL Editor

-- Table 1: companies
CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Table 2: document_schemas (schema registry)
CREATE TABLE IF NOT EXISTS document_schemas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_type TEXT UNIQUE NOT NULL,
    output_format JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Table 3: cases
CREATE TABLE IF NOT EXISTS cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'pending',
    extracted_data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(company_id)
);

-- ========================================
-- Seed Data
-- ========================================

-- Demo company
INSERT INTO companies (name) VALUES ('Acme Corp')
ON CONFLICT DO NOTHING;

-- Bank statement schema
INSERT INTO document_schemas (document_type, output_format) VALUES (
    'bank_statement',
    '{
        "type": "object",
        "properties": {
            "account_holder": {"type": "string"},
            "account_number": {"type": "string"},
            "bank_name": {"type": "string"},
            "statement_period": {"type": "string"},
            "transactions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string"},
                        "description": {"type": "string"},
                        "debit": {"type": "number"},
                        "credit": {"type": "number"},
                        "balance": {"type": "number"}
                    }
                }
            }
        }
    }'
) ON CONFLICT (document_type) DO NOTHING;

-- Salary slip schema
INSERT INTO document_schemas (document_type, output_format) VALUES (
    'salary_slip',
    '{
        "type": "object",
        "properties": {
            "employee_name": {"type": "string"},
            "employee_id": {"type": "string"},
            "company_name": {"type": "string"},
            "month": {"type": "string"},
            "basic_salary": {"type": "number"},
            "allowances": {"type": "number"},
            "deductions": {"type": "number"},
            "net_salary": {"type": "number"}
        }
    }'
) ON CONFLICT (document_type) DO NOTHING;

-- Invoice schema
INSERT INTO document_schemas (document_type, output_format) VALUES (
    'invoice',
    '{
        "type": "object",
        "properties": {
            "invoice_number": {"type": "string"},
            "vendor_name": {"type": "string"},
            "buyer_name": {"type": "string"},
            "invoice_date": {"type": "string"},
            "due_date": {"type": "string"},
            "total_amount": {"type": "number"},
            "tax_amount": {"type": "number"},
            "line_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "quantity": {"type": "number"},
                        "unit_price": {"type": "number"},
                        "amount": {"type": "number"}
                    }
                }
            }
        }
    }'
) ON CONFLICT (document_type) DO NOTHING;

-- Tax return schema
INSERT INTO document_schemas (document_type, output_format) VALUES (
    'tax_return',
    '{
        "type": "object",
        "properties": {
            "assessee_name": {"type": "string"},
            "pan_number": {"type": "string"},
            "assessment_year": {"type": "string"},
            "total_income": {"type": "number"},
            "tax_payable": {"type": "number"},
            "tax_paid": {"type": "number"},
            "refund_due": {"type": "number"}
        }
    }'
) ON CONFLICT (document_type) DO NOTHING;

-- Identity document schema
INSERT INTO document_schemas (document_type, output_format) VALUES (
    'identity_document',
    '{
        "type": "object",
        "properties": {
            "document_type": {"type": "string"},
            "full_name": {"type": "string"},
            "date_of_birth": {"type": "string"},
            "id_number": {"type": "string"},
            "address": {"type": "string"},
            "issue_date": {"type": "string"},
            "expiry_date": {"type": "string"}
        }
    }'
) ON CONFLICT (document_type) DO NOTHING;
