#!/usr/bin/env python3
"""
HubSpot Audit - CSV Join Script
Joins workflow consolidations with:
1. Workflow xlsx file (for enabled status via Flow ID)
2. HubSpot property files (contact, company, deal) via Internal Name
3. Salesforce field mapping files via HubSpot Field Name

Properties appearing in BOTH HubSpot properties AND Salesforce mappings are marked as "key fields"
"""

import pandas as pd
import csv
import os
from collections import defaultdict

# File paths
BASE_DIR = "/home/user/rho-audit/hubspot"
WORKFLOW_CONSOLIDATIONS = os.path.join(BASE_DIR, "Copy of Rho - Hubspot Workflow Consolidations - Workflow Consolidations.csv")
WORKFLOW_XLSX = os.path.join(BASE_DIR, "hubspot-listing-lib-exports-all-workflows-2025-11-24.xlsx")
HUBSPOT_CONTACT_PROPS = os.path.join(BASE_DIR, "hubspot_contact_properties.csv")
HUBSPOT_COMPANY_PROPS = os.path.join(BASE_DIR, "hubspot_company_properties.csv")
HUBSPOT_DEAL_PROPS = os.path.join(BASE_DIR, "hubspot_deal_properties.csv")
SF_CONTACT_MAPPINGS = os.path.join(BASE_DIR, "SALESFORCE_CONTACT_field_mappings (4).csv")
SF_COMPANY_MAPPINGS = os.path.join(BASE_DIR, "SALESFORCE_COMPANY_field_mappings (3).csv")
SF_DEAL_MAPPINGS = os.path.join(BASE_DIR, "SALESFORCE_DEAL_field_mappings (4).csv")
OUTPUT_FILE = os.path.join(BASE_DIR, "audit_consolidated_workflows.csv")


def load_workflow_xlsx():
    """Load the workflow xlsx file and create a lookup by Flow ID"""
    print("Loading workflow xlsx file...")
    df = pd.read_excel(WORKFLOW_XLSX)

    # Create lookup dictionary by Flow ID
    workflow_lookup = {}
    for _, row in df.iterrows():
        flow_id = str(int(row['Flow ID'])) if pd.notna(row['Flow ID']) else None
        if flow_id:
            workflow_lookup[flow_id] = {
                'xlsx_on_or_off': row.get('On or Off', ''),
                'xlsx_enrolled_total': row.get('Enrolled total', ''),
                'xlsx_enrolled_unique': row.get('Enrolled unique', ''),
                'xlsx_enrolled_last_7_days': row.get('Enrolled last 7-days', ''),
                'xlsx_currently_enrolled': row.get('Currently Enrolled', ''),
                'xlsx_created_on': str(row.get('Created on', '')),
                'xlsx_updated_on': str(row.get('Updated on', '')),
                'xlsx_created_by': row.get('Created by', ''),
                'xlsx_updated_by': row.get('Updated by', ''),
                'xlsx_object_type': row.get('Object type', ''),
                'xlsx_trigger_type': row.get('Trigger Type', ''),
                'xlsx_description': row.get('Description', ''),
                'xlsx_action_type': row.get('Action type', ''),
                'xlsx_folder': row.get('Folder', ''),
                'xlsx_current_issues': row.get('Current issues', ''),
                'xlsx_may_use_credits': row.get('May use credits', ''),
            }
    print(f"  Loaded {len(workflow_lookup)} workflows from xlsx")
    return workflow_lookup


def load_hubspot_properties():
    """Load all HubSpot property files and create lookup by Internal Name"""
    print("Loading HubSpot property files...")

    property_lookup = {}  # internal_name -> property info

    files = [
        (HUBSPOT_CONTACT_PROPS, 'contact'),
        (HUBSPOT_COMPANY_PROPS, 'company'),
        (HUBSPOT_DEAL_PROPS, 'deal'),
    ]

    for filepath, obj_type in files:
        df = pd.read_csv(filepath)
        count = 0
        for _, row in df.iterrows():
            internal_name = str(row.get('Internal name', '')).strip().lower()
            if internal_name and internal_name != 'nan':
                if internal_name not in property_lookup:
                    property_lookup[internal_name] = {
                        'hs_name': row.get('Name', ''),
                        'hs_type': row.get('Type', ''),
                        'hs_group': row.get('Group name', ''),
                        'hs_description': row.get('Description', ''),
                        'hs_hubspot_defined': row.get('HubSpot defined', ''),
                        'hs_fill_rate': row.get('Fill rate', ''),
                        'hs_usages': row.get('Usages', ''),
                        'hs_object_types': set([obj_type]),
                    }
                else:
                    property_lookup[internal_name]['hs_object_types'].add(obj_type)
                count += 1
        print(f"  Loaded {count} properties from {obj_type} properties file")

    print(f"  Total unique HubSpot properties: {len(property_lookup)}")
    return property_lookup


def load_salesforce_mappings():
    """Load all Salesforce field mapping files and create lookup by HubSpot Field Name"""
    print("Loading Salesforce field mapping files...")

    sf_lookup = {}  # hubspot_field_name -> mapping info

    files = [
        (SF_CONTACT_MAPPINGS, 'contact'),
        (SF_COMPANY_MAPPINGS, 'company'),
        (SF_DEAL_MAPPINGS, 'deal'),
    ]

    for filepath, obj_type in files:
        df = pd.read_csv(filepath)
        count = 0
        for _, row in df.iterrows():
            hs_field = str(row.get('HubSpot Field Name', '')).strip().lower()
            if hs_field and hs_field != 'nan':
                if hs_field not in sf_lookup:
                    sf_lookup[hs_field] = {
                        'sf_field_name': row.get('Salesforce Field Name', ''),
                        'sf_sync_rule': row.get('Sync Rule', ''),
                        'sf_object_types': set([obj_type]),
                    }
                else:
                    sf_lookup[hs_field]['sf_object_types'].add(obj_type)
                count += 1
        print(f"  Loaded {count} mappings from {obj_type} Salesforce mappings file")

    print(f"  Total unique Salesforce-mapped HubSpot fields: {len(sf_lookup)}")
    return sf_lookup


def parse_properties(prop_string):
    """Parse a comma-separated property string into a list"""
    if not prop_string or pd.isna(prop_string) or prop_string == '':
        return []

    # Split by comma and clean up each property
    props = [p.strip().lower() for p in str(prop_string).split(',')]
    return [p for p in props if p]


def analyze_properties(prop_list, hs_lookup, sf_lookup):
    """
    Analyze a list of properties against HubSpot properties and Salesforce mappings.
    Returns lists of matched HubSpot props, SF-mapped props, and key fields (both).
    """
    hs_matched = []
    sf_matched = []
    key_fields = []
    unmatched = []

    for prop in prop_list:
        in_hs = prop in hs_lookup
        in_sf = prop in sf_lookup

        if in_hs and in_sf:
            key_fields.append(prop)
        elif in_hs:
            hs_matched.append(prop)
        elif in_sf:
            sf_matched.append(prop)
        else:
            unmatched.append(prop)

    return {
        'hs_only': hs_matched,
        'sf_only': sf_matched,
        'key_fields': key_fields,
        'unmatched': unmatched,
    }


def main():
    print("=" * 60)
    print("HubSpot Audit - CSV Join Script")
    print("=" * 60)
    print()

    # Load all lookup data
    workflow_xlsx_lookup = load_workflow_xlsx()
    hs_property_lookup = load_hubspot_properties()
    sf_mapping_lookup = load_salesforce_mappings()

    print()
    print("Loading workflow consolidations CSV...")

    # Read the main workflow consolidations file
    df = pd.read_csv(WORKFLOW_CONSOLIDATIONS)
    print(f"  Loaded {len(df)} workflows from consolidations file")
    print(f"  Columns: {df.columns.tolist()}")

    # Clean up FlowId column - first column
    df['FlowId'] = df['FlowId'].astype(str).str.strip()

    print()
    print("Processing joins and analysis...")

    # Initialize new columns
    new_columns = {
        # From xlsx join
        'XLSX_Enabled': [],
        'XLSX_Enrolled_Total': [],
        'XLSX_Currently_Enrolled': [],
        'XLSX_Object_Type': [],
        'XLSX_Trigger_Type': [],
        'XLSX_Updated_On': [],
        'XLSX_Description': [],
        'XLSX_Found': [],

        # Property analysis - Writes
        'Writes_Key_Fields': [],
        'Writes_HubSpot_Only_Props': [],
        'Writes_Salesforce_Only_Props': [],
        'Writes_Unmatched_Props': [],
        'Writes_Key_Fields_Count': [],
        'Writes_Total_Props_Count': [],

        # Property analysis - Reads
        'Reads_Key_Fields': [],
        'Reads_HubSpot_Only_Props': [],
        'Reads_Salesforce_Only_Props': [],
        'Reads_Unmatched_Props': [],
        'Reads_Key_Fields_Count': [],
        'Reads_Total_Props_Count': [],

        # Combined metrics
        'Total_Key_Fields': [],
        'Uses_Salesforce_Connected_Props': [],
    }

    # Process each workflow
    xlsx_matches = 0
    for idx, row in df.iterrows():
        flow_id = str(row['FlowId']).strip()

        # Join with xlsx data
        xlsx_data = workflow_xlsx_lookup.get(flow_id, {})
        xlsx_found = bool(xlsx_data)
        if xlsx_found:
            xlsx_matches += 1

        new_columns['XLSX_Enabled'].append(xlsx_data.get('xlsx_on_or_off', ''))
        new_columns['XLSX_Enrolled_Total'].append(xlsx_data.get('xlsx_enrolled_total', ''))
        new_columns['XLSX_Currently_Enrolled'].append(xlsx_data.get('xlsx_currently_enrolled', ''))
        new_columns['XLSX_Object_Type'].append(xlsx_data.get('xlsx_object_type', ''))
        new_columns['XLSX_Trigger_Type'].append(xlsx_data.get('xlsx_trigger_type', ''))
        new_columns['XLSX_Updated_On'].append(xlsx_data.get('xlsx_updated_on', ''))
        new_columns['XLSX_Description'].append(xlsx_data.get('xlsx_description', ''))
        new_columns['XLSX_Found'].append(xlsx_found)

        # Parse and analyze Writes Properties
        writes_props = parse_properties(row.get('Writes Properties', ''))
        writes_analysis = analyze_properties(writes_props, hs_property_lookup, sf_mapping_lookup)

        new_columns['Writes_Key_Fields'].append(', '.join(writes_analysis['key_fields']))
        new_columns['Writes_HubSpot_Only_Props'].append(', '.join(writes_analysis['hs_only']))
        new_columns['Writes_Salesforce_Only_Props'].append(', '.join(writes_analysis['sf_only']))
        new_columns['Writes_Unmatched_Props'].append(', '.join(writes_analysis['unmatched']))
        new_columns['Writes_Key_Fields_Count'].append(len(writes_analysis['key_fields']))
        new_columns['Writes_Total_Props_Count'].append(len(writes_props))

        # Parse and analyze Reads Properties
        reads_props = parse_properties(row.get('Reads Properties', ''))
        reads_analysis = analyze_properties(reads_props, hs_property_lookup, sf_mapping_lookup)

        new_columns['Reads_Key_Fields'].append(', '.join(reads_analysis['key_fields']))
        new_columns['Reads_HubSpot_Only_Props'].append(', '.join(reads_analysis['hs_only']))
        new_columns['Reads_Salesforce_Only_Props'].append(', '.join(reads_analysis['sf_only']))
        new_columns['Reads_Unmatched_Props'].append(', '.join(reads_analysis['unmatched']))
        new_columns['Reads_Key_Fields_Count'].append(len(reads_analysis['key_fields']))
        new_columns['Reads_Total_Props_Count'].append(len(reads_props))

        # Combined metrics
        all_key_fields = set(writes_analysis['key_fields'] + reads_analysis['key_fields'])
        all_sf_connected = set(
            writes_analysis['key_fields'] + writes_analysis['sf_only'] +
            reads_analysis['key_fields'] + reads_analysis['sf_only']
        )

        new_columns['Total_Key_Fields'].append(len(all_key_fields))
        new_columns['Uses_Salesforce_Connected_Props'].append(len(all_sf_connected) > 0)

    print(f"  Matched {xlsx_matches}/{len(df)} workflows with xlsx data")

    # Add new columns to dataframe
    for col_name, col_data in new_columns.items():
        df[col_name] = col_data

    # Reorder columns to put important ones first
    priority_cols = [
        'FlowId', 'Name', 'Enabled', 'XLSX_Enabled', 'XLSX_Found',
        'Recommended Action', 'Total Enrolled', 'XLSX_Enrolled_Total', 'XLSX_Currently_Enrolled',
        'XLSX_Object_Type', 'XLSX_Trigger_Type', 'XLSX_Updated_On',
        'Uses_Salesforce_Connected_Props', 'Total_Key_Fields',
        'Writes_Key_Fields', 'Writes_Key_Fields_Count', 'Writes Properties',
        'Writes_HubSpot_Only_Props', 'Writes_Salesforce_Only_Props', 'Writes_Unmatched_Props',
        'Reads_Key_Fields', 'Reads_Key_Fields_Count', 'Reads Properties',
        'Reads_HubSpot_Only_Props', 'Reads_Salesforce_Only_Props', 'Reads_Unmatched_Props',
    ]

    other_cols = [c for c in df.columns if c not in priority_cols]
    final_cols = [c for c in priority_cols if c in df.columns] + other_cols
    df = df[final_cols]

    # Save output
    df.to_csv(OUTPUT_FILE, index=False)
    print()
    print(f"Output saved to: {OUTPUT_FILE}")

    # Print summary statistics
    print()
    print("=" * 60)
    print("SUMMARY STATISTICS")
    print("=" * 60)

    # Enabled status breakdown
    print("\n--- Workflow Enabled Status (from XLSX) ---")
    enabled_counts = df['XLSX_Enabled'].value_counts(dropna=False)
    for status, count in enabled_counts.items():
        print(f"  {status}: {count}")

    # Recommended Action breakdown
    print("\n--- Recommended Actions ---")
    action_counts = df['Recommended Action'].value_counts(dropna=False)
    for action, count in action_counts.items():
        print(f"  {action}: {count}")

    # Salesforce connection breakdown
    print("\n--- Salesforce Connected Properties Usage ---")
    sf_connected = df['Uses_Salesforce_Connected_Props'].value_counts()
    for status, count in sf_connected.items():
        print(f"  Uses SF-connected props: {status}: {count}")

    # Key fields summary
    print("\n--- Key Fields Summary (properties in both HS & SF) ---")
    print(f"  Workflows with key fields: {(df['Total_Key_Fields'] > 0).sum()}")
    print(f"  Workflows without key fields: {(df['Total_Key_Fields'] == 0).sum()}")
    print(f"  Average key fields per workflow: {df['Total_Key_Fields'].mean():.2f}")
    print(f"  Max key fields in a workflow: {df['Total_Key_Fields'].max()}")

    # Cross-tabulation: Enabled vs Uses SF Connected Props
    print("\n--- Enabled Status vs Salesforce Connection ---")
    cross_tab = pd.crosstab(df['XLSX_Enabled'], df['Uses_Salesforce_Connected_Props'])
    print(cross_tab)

    # List workflows that are enabled AND use Salesforce-connected properties
    print("\n--- Enabled Workflows Using Salesforce-Connected Properties ---")
    enabled_sf = df[(df['XLSX_Enabled'] == True) & (df['Uses_Salesforce_Connected_Props'] == True)]
    print(f"  Total: {len(enabled_sf)} workflows")

    # High-priority audit items: enabled workflows with key fields
    print("\n--- HIGH PRIORITY: Enabled Workflows with Key Fields ---")
    high_priority = df[(df['XLSX_Enabled'] == True) & (df['Total_Key_Fields'] > 0)].sort_values('Total_Key_Fields', ascending=False)
    print(f"  Total: {len(high_priority)} workflows")
    if len(high_priority) > 0:
        print("\n  Top 10 by key fields count:")
        for _, row in high_priority.head(10).iterrows():
            print(f"    - {row['Name'][:60]}... | Key Fields: {row['Total_Key_Fields']} | Writes: {row['Writes_Key_Fields'][:40] if row['Writes_Key_Fields'] else 'N/A'}...")

    print("\n" + "=" * 60)
    print("AUDIT COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
