#!/usr/bin/env python3
"""
HubSpot Audit - CSV Join Script (Enhanced)
Joins workflow consolidations with:
1. Workflow xlsx file (for enabled status via Flow ID)
2. HubSpot property files (contact, company, deal) via Internal Name - includes Friendly Names
3. Salesforce field mapping files via HubSpot Field Name

Properties appearing in BOTH HubSpot properties AND Salesforce mappings are marked as "key fields"

Outputs:
1. audit_consolidated_workflows.csv - Enhanced workflow table
2. audit_property_usage.csv - Property-centric analysis with workflow references
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
OUTPUT_WORKFLOWS = os.path.join(BASE_DIR, "audit_consolidated_workflows.csv")
OUTPUT_PROPERTIES = os.path.join(BASE_DIR, "audit_property_usage.csv")


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
                'XLSX_On_Or_Off': row.get('On or Off', ''),
                'XLSX_Enrolled_Total': row.get('Enrolled total', ''),
                'XLSX_Enrolled_Unique': row.get('Enrolled unique', ''),
                'XLSX_Enrolled_Last_7_Days': row.get('Enrolled last 7-days', ''),
                'XLSX_Currently_Enrolled': row.get('Currently Enrolled', ''),
                'XLSX_Created_On': str(row.get('Created on', '')),
                'XLSX_Updated_On': str(row.get('Updated on', '')),
                'XLSX_Created_By': row.get('Created by', ''),
                'XLSX_Updated_By': row.get('Updated by', ''),
                'XLSX_Object_Type': row.get('Object type', ''),
                'XLSX_Trigger_Type': row.get('Trigger Type', ''),
                'XLSX_Description': row.get('Description', ''),
                'XLSX_Action_Type': row.get('Action type', ''),
                'XLSX_Folder': row.get('Folder', ''),
                'XLSX_Current_Issues': row.get('Current issues', ''),
                'XLSX_Current_Issue_Count': row.get('Current Issue Count', ''),
                'XLSX_May_Use_Credits': row.get('May use credits', ''),
                'XLSX_Record_ID': row.get('Record ID', ''),
            }
    print(f"  Loaded {len(workflow_lookup)} workflows from xlsx")
    return workflow_lookup


def load_hubspot_properties():
    """Load all HubSpot property files and create lookup by Internal Name with full details"""
    print("Loading HubSpot property files...")

    property_lookup = {}  # internal_name -> property info

    files = [
        (HUBSPOT_CONTACT_PROPS, 'Contact'),
        (HUBSPOT_COMPANY_PROPS, 'Company'),
        (HUBSPOT_DEAL_PROPS, 'Deal'),
    ]

    for filepath, obj_type in files:
        df = pd.read_csv(filepath)
        count = 0
        for _, row in df.iterrows():
            internal_name = str(row.get('Internal name', '')).strip().lower()
            if internal_name and internal_name != 'nan':
                if internal_name not in property_lookup:
                    property_lookup[internal_name] = {
                        'HS_Friendly_Name': str(row.get('Name', '')),
                        'HS_Internal_Name': internal_name,
                        'HS_Type': str(row.get('Type', '')),
                        'HS_Group_Name': str(row.get('Group name', '')),
                        'HS_Description': str(row.get('Description', '')),
                        'HS_Form_Field': str(row.get('Form field', '')),
                        'HS_Options': str(row.get('Options', '')),
                        'HS_Read_Only_Value': str(row.get('Read only value', '')),
                        'HS_Read_Only_Definition': str(row.get('Read only definition', '')),
                        'HS_Calculated': str(row.get('Calculated', '')),
                        'HS_External_Options': str(row.get('External options', '')),
                        'HS_Deleted': str(row.get('Deleted', '')),
                        'HS_HubSpot_Defined': str(row.get('HubSpot defined', '')),
                        'HS_Created_User': str(row.get('Created user', '')),
                        'HS_Usages': str(row.get('Usages', '')),
                        'HS_Fill_Rate': str(row.get('Fill rate', '')),
                        'HS_Last_Updated_Time': str(row.get('Last Updated Time', '')),
                        'HS_Update_Source': str(row.get('Update Source', '')),
                        'HS_Object_Types': [obj_type],
                    }
                else:
                    if obj_type not in property_lookup[internal_name]['HS_Object_Types']:
                        property_lookup[internal_name]['HS_Object_Types'].append(obj_type)
                count += 1
        print(f"  Loaded {count} properties from {obj_type} properties file")

    print(f"  Total unique HubSpot properties: {len(property_lookup)}")
    return property_lookup


def load_salesforce_mappings():
    """Load all Salesforce field mapping files and create lookup by HubSpot Field Name"""
    print("Loading Salesforce field mapping files...")

    sf_lookup = {}  # hubspot_field_name -> mapping info

    files = [
        (SF_CONTACT_MAPPINGS, 'Contact'),
        (SF_COMPANY_MAPPINGS, 'Company'),
        (SF_DEAL_MAPPINGS, 'Deal'),
    ]

    for filepath, obj_type in files:
        df = pd.read_csv(filepath)
        count = 0
        for _, row in df.iterrows():
            hs_field = str(row.get('HubSpot Field Name', '')).strip().lower()
            if hs_field and hs_field != 'nan':
                if hs_field not in sf_lookup:
                    sf_lookup[hs_field] = {
                        'SF_Field_Name': str(row.get('Salesforce Field Name', '')),
                        'SF_Sync_Rule': str(row.get('Sync Rule', '')),
                        'SF_Object_Types': [obj_type],
                    }
                else:
                    if obj_type not in sf_lookup[hs_field]['SF_Object_Types']:
                        sf_lookup[hs_field]['SF_Object_Types'].append(obj_type)
                    # Append additional SF field names if different
                    existing_sf_name = sf_lookup[hs_field]['SF_Field_Name']
                    new_sf_name = str(row.get('Salesforce Field Name', ''))
                    if new_sf_name and new_sf_name not in existing_sf_name:
                        sf_lookup[hs_field]['SF_Field_Name'] = f"{existing_sf_name}; {new_sf_name}"
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


def get_friendly_name_mapping(prop_list, hs_lookup):
    """
    Create a mapping string showing: Friendly Name (internal_name)
    """
    mappings = []
    for prop in prop_list:
        if prop in hs_lookup:
            friendly = hs_lookup[prop]['HS_Friendly_Name']
            if friendly and friendly != 'nan':
                mappings.append(f"{friendly} ({prop})")
            else:
                mappings.append(prop)
        else:
            mappings.append(prop)
    return '; '.join(mappings)


def analyze_properties(prop_list, hs_lookup, sf_lookup):
    """
    Analyze a list of properties against HubSpot properties and Salesforce mappings.
    Returns detailed analysis including friendly names.
    """
    hs_matched = []
    sf_matched = []
    key_fields = []
    unmatched = []

    key_fields_with_names = []
    hs_only_with_names = []
    sf_only_with_names = []

    for prop in prop_list:
        in_hs = prop in hs_lookup
        in_sf = prop in sf_lookup

        friendly_name = hs_lookup[prop]['HS_Friendly_Name'] if in_hs else ''
        sf_field = sf_lookup[prop]['SF_Field_Name'] if in_sf else ''

        if in_hs and in_sf:
            key_fields.append(prop)
            key_fields_with_names.append(f"{friendly_name} > {prop} > SF:{sf_field}")
        elif in_hs:
            hs_matched.append(prop)
            hs_only_with_names.append(f"{friendly_name} ({prop})")
        elif in_sf:
            sf_matched.append(prop)
            sf_only_with_names.append(f"{prop} > SF:{sf_field}")
        else:
            unmatched.append(prop)

    return {
        'hs_only': hs_matched,
        'sf_only': sf_matched,
        'key_fields': key_fields,
        'unmatched': unmatched,
        'key_fields_with_names': key_fields_with_names,
        'hs_only_with_names': hs_only_with_names,
        'sf_only_with_names': sf_only_with_names,
    }


def build_property_usage_table(workflow_df, hs_lookup, sf_lookup):
    """
    Build a property-centric usage table showing:
    - All properties used across workflows
    - Which workflows read/write each property
    - HubSpot property details
    - Salesforce mapping details
    """
    print("\nBuilding property usage analysis table...")

    # Track property usage across all workflows
    property_usage = defaultdict(lambda: {
        'workflows_writing': [],
        'workflows_reading': [],
        'workflow_ids_writing': [],
        'workflow_ids_reading': [],
    })

    for _, row in workflow_df.iterrows():
        flow_id = str(row['FlowId']).strip()
        workflow_name = str(row['Name'])

        # Track writes
        writes = parse_properties(row.get('Writes Properties', ''))
        for prop in writes:
            property_usage[prop]['workflows_writing'].append(workflow_name)
            property_usage[prop]['workflow_ids_writing'].append(flow_id)

        # Track reads
        reads = parse_properties(row.get('Reads Properties', ''))
        for prop in reads:
            property_usage[prop]['workflows_reading'].append(workflow_name)
            property_usage[prop]['workflow_ids_reading'].append(flow_id)

    # Build the output table
    rows = []
    for internal_name, usage in sorted(property_usage.items()):
        hs_data = hs_lookup.get(internal_name, {})
        sf_data = sf_lookup.get(internal_name, {})

        in_hs = internal_name in hs_lookup
        in_sf = internal_name in sf_lookup

        # Determine property classification
        if in_hs and in_sf:
            classification = "KEY FIELD (HS + SF)"
        elif in_hs:
            classification = "HubSpot Only"
        elif in_sf:
            classification = "Salesforce Mapped Only"
        else:
            classification = "Unmatched/Custom"

        total_writes = len(usage['workflows_writing'])
        total_reads = len(usage['workflows_reading'])
        total_references = total_writes + total_reads

        rows.append({
            # Classification & Counts (First)
            'Classification': classification,
            'Total_References': total_references,
            'Total_Workflows_Writing': total_writes,
            'Total_Workflows_Reading': total_reads,
            'Is_Key_Field': in_hs and in_sf,
            'In_HubSpot_Properties': in_hs,
            'In_Salesforce_Mappings': in_sf,

            # Property Identification
            'Internal_Name': internal_name,
            'HS_Friendly_Name': hs_data.get('HS_Friendly_Name', ''),

            # HubSpot Property Details
            'HS_Type': hs_data.get('HS_Type', ''),
            'HS_Group_Name': hs_data.get('HS_Group_Name', ''),
            'HS_Description': hs_data.get('HS_Description', ''),
            'HS_Object_Types': ', '.join(hs_data.get('HS_Object_Types', [])),
            'HS_Form_Field': hs_data.get('HS_Form_Field', ''),
            'HS_Read_Only_Value': hs_data.get('HS_Read_Only_Value', ''),
            'HS_Calculated': hs_data.get('HS_Calculated', ''),
            'HS_HubSpot_Defined': hs_data.get('HS_HubSpot_Defined', ''),
            'HS_Created_User': hs_data.get('HS_Created_User', ''),
            'HS_Usages': hs_data.get('HS_Usages', ''),
            'HS_Fill_Rate': hs_data.get('HS_Fill_Rate', ''),
            'HS_Last_Updated_Time': hs_data.get('HS_Last_Updated_Time', ''),
            'HS_Update_Source': hs_data.get('HS_Update_Source', ''),

            # Salesforce Mapping Details
            'SF_Field_Name': sf_data.get('SF_Field_Name', ''),
            'SF_Sync_Rule': sf_data.get('SF_Sync_Rule', ''),
            'SF_Object_Types': ', '.join(sf_data.get('SF_Object_Types', [])),

            # Workflow References (Last)
            'Workflows_Writing': '; '.join(usage['workflows_writing'][:20]) + ('...' if total_writes > 20 else ''),
            'Workflow_IDs_Writing': ', '.join(usage['workflow_ids_writing'][:20]) + ('...' if total_writes > 20 else ''),
            'Workflows_Reading': '; '.join(usage['workflows_reading'][:20]) + ('...' if total_reads > 20 else ''),
            'Workflow_IDs_Reading': ', '.join(usage['workflow_ids_reading'][:20]) + ('...' if total_reads > 20 else ''),
        })

    property_df = pd.DataFrame(rows)

    # Sort by total references descending
    property_df = property_df.sort_values(['Is_Key_Field', 'Total_References'], ascending=[False, False])

    print(f"  Built property usage table with {len(property_df)} unique properties")
    return property_df


def main():
    print("=" * 60)
    print("HubSpot Audit - CSV Join Script (Enhanced)")
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

    # Store original columns for later
    original_columns = df.columns.tolist()
    print(f"  Original columns: {original_columns}")

    # Clean up FlowId column
    df['FlowId'] = df['FlowId'].astype(str).str.strip()

    print()
    print("Processing joins and analysis...")

    # Initialize new columns dictionary (will be added as prefix)
    new_data = []

    # Process each workflow
    xlsx_matches = 0
    for idx, row in df.iterrows():
        flow_id = str(row['FlowId']).strip()
        workflow_name = str(row['Name'])

        # Join with xlsx data
        xlsx_data = workflow_xlsx_lookup.get(flow_id, {})
        xlsx_found = bool(xlsx_data)
        if xlsx_found:
            xlsx_matches += 1

        # Parse and analyze Writes Properties
        writes_props = parse_properties(row.get('Writes Properties', ''))
        writes_analysis = analyze_properties(writes_props, hs_property_lookup, sf_mapping_lookup)

        # Parse and analyze Reads Properties
        reads_props = parse_properties(row.get('Reads Properties', ''))
        reads_analysis = analyze_properties(reads_props, hs_property_lookup, sf_mapping_lookup)

        # Combined metrics
        all_key_fields = set(writes_analysis['key_fields'] + reads_analysis['key_fields'])
        all_sf_connected = set(
            writes_analysis['key_fields'] + writes_analysis['sf_only'] +
            reads_analysis['key_fields'] + reads_analysis['sf_only']
        )

        row_data = {
            # === NEW ANALYSIS FIELDS (First Set) ===
            'AUDIT_Uses_SF_Connected_Props': len(all_sf_connected) > 0,
            'AUDIT_Total_Key_Fields_Count': len(all_key_fields),
            'AUDIT_XLSX_Match_Found': xlsx_found,

            # Key Fields Analysis with Friendly Names
            'AUDIT_Writes_Key_Fields_Detailed': '; '.join(writes_analysis['key_fields_with_names']),
            'AUDIT_Writes_Key_Fields_Count': len(writes_analysis['key_fields']),
            'AUDIT_Writes_Key_Fields_List': ', '.join(writes_analysis['key_fields']),

            'AUDIT_Reads_Key_Fields_Detailed': '; '.join(reads_analysis['key_fields_with_names']),
            'AUDIT_Reads_Key_Fields_Count': len(reads_analysis['key_fields']),
            'AUDIT_Reads_Key_Fields_List': ', '.join(reads_analysis['key_fields']),

            # HubSpot Only Properties with Friendly Names
            'AUDIT_Writes_HS_Only_Detailed': '; '.join(writes_analysis['hs_only_with_names']),
            'AUDIT_Writes_HS_Only_Count': len(writes_analysis['hs_only']),
            'AUDIT_Reads_HS_Only_Detailed': '; '.join(reads_analysis['hs_only_with_names']),
            'AUDIT_Reads_HS_Only_Count': len(reads_analysis['hs_only']),

            # Salesforce Only Properties
            'AUDIT_Writes_SF_Only_Detailed': '; '.join(writes_analysis['sf_only_with_names']),
            'AUDIT_Writes_SF_Only_Count': len(writes_analysis['sf_only']),
            'AUDIT_Reads_SF_Only_Detailed': '; '.join(reads_analysis['sf_only_with_names']),
            'AUDIT_Reads_SF_Only_Count': len(reads_analysis['sf_only']),

            # Unmatched Properties
            'AUDIT_Writes_Unmatched': ', '.join(writes_analysis['unmatched']),
            'AUDIT_Writes_Unmatched_Count': len(writes_analysis['unmatched']),
            'AUDIT_Reads_Unmatched': ', '.join(reads_analysis['unmatched']),
            'AUDIT_Reads_Unmatched_Count': len(reads_analysis['unmatched']),

            # Total property counts
            'AUDIT_Writes_Total_Props_Count': len(writes_props),
            'AUDIT_Reads_Total_Props_Count': len(reads_props),
        }

        # === XLSX DATA (Appended After Original) ===
        xlsx_fields = {
            'XLSX_On_Or_Off': xlsx_data.get('XLSX_On_Or_Off', ''),
            'XLSX_Enrolled_Total': xlsx_data.get('XLSX_Enrolled_Total', ''),
            'XLSX_Enrolled_Unique': xlsx_data.get('XLSX_Enrolled_Unique', ''),
            'XLSX_Enrolled_Last_7_Days': xlsx_data.get('XLSX_Enrolled_Last_7_Days', ''),
            'XLSX_Currently_Enrolled': xlsx_data.get('XLSX_Currently_Enrolled', ''),
            'XLSX_Object_Type': xlsx_data.get('XLSX_Object_Type', ''),
            'XLSX_Trigger_Type': xlsx_data.get('XLSX_Trigger_Type', ''),
            'XLSX_Created_On': xlsx_data.get('XLSX_Created_On', ''),
            'XLSX_Updated_On': xlsx_data.get('XLSX_Updated_On', ''),
            'XLSX_Created_By': xlsx_data.get('XLSX_Created_By', ''),
            'XLSX_Updated_By': xlsx_data.get('XLSX_Updated_By', ''),
            'XLSX_Description': xlsx_data.get('XLSX_Description', ''),
            'XLSX_Action_Type': xlsx_data.get('XLSX_Action_Type', ''),
            'XLSX_Folder': xlsx_data.get('XLSX_Folder', ''),
            'XLSX_Current_Issues': xlsx_data.get('XLSX_Current_Issues', ''),
            'XLSX_Current_Issue_Count': xlsx_data.get('XLSX_Current_Issue_Count', ''),
            'XLSX_May_Use_Credits': xlsx_data.get('XLSX_May_Use_Credits', ''),
            'XLSX_Record_ID': xlsx_data.get('XLSX_Record_ID', ''),
        }

        row_data.update(xlsx_fields)
        new_data.append(row_data)

    print(f"  Matched {xlsx_matches}/{len(df)} workflows with xlsx data")

    # Create new columns dataframe
    new_cols_df = pd.DataFrame(new_data)

    # Define column order:
    # 1. AUDIT_ columns (new analysis fields)
    # 2. Original workflow consolidation columns
    # 3. XLSX_ columns (appended data)

    audit_cols = [c for c in new_cols_df.columns if c.startswith('AUDIT_')]
    xlsx_cols = [c for c in new_cols_df.columns if c.startswith('XLSX_')]

    # Build final dataframe with correct column order
    final_df = pd.concat([
        new_cols_df[audit_cols].reset_index(drop=True),
        df.reset_index(drop=True),
        new_cols_df[xlsx_cols].reset_index(drop=True)
    ], axis=1)

    # Save workflow output
    final_df.to_csv(OUTPUT_WORKFLOWS, index=False)
    print()
    print(f"Workflow output saved to: {OUTPUT_WORKFLOWS}")

    # Build and save property usage table
    property_df = build_property_usage_table(df, hs_property_lookup, sf_mapping_lookup)
    property_df.to_csv(OUTPUT_PROPERTIES, index=False)
    print(f"Property usage output saved to: {OUTPUT_PROPERTIES}")

    # Print summary statistics
    print()
    print("=" * 60)
    print("SUMMARY STATISTICS")
    print("=" * 60)

    # Enabled status breakdown
    print("\n--- Workflow Enabled Status (from XLSX) ---")
    enabled_counts = final_df['XLSX_On_Or_Off'].value_counts(dropna=False)
    for status, count in enabled_counts.items():
        print(f"  {status}: {count}")

    # Recommended Action breakdown
    print("\n--- Recommended Actions ---")
    action_counts = final_df['Recommended Action'].value_counts(dropna=False)
    for action, count in action_counts.items():
        print(f"  {action}: {count}")

    # Salesforce connection breakdown
    print("\n--- Salesforce Connected Properties Usage ---")
    sf_connected = final_df['AUDIT_Uses_SF_Connected_Props'].value_counts()
    for status, count in sf_connected.items():
        print(f"  Uses SF-connected props: {status}: {count}")

    # Key fields summary
    print("\n--- Key Fields Summary (properties in both HS & SF) ---")
    print(f"  Workflows with key fields: {(final_df['AUDIT_Total_Key_Fields_Count'] > 0).sum()}")
    print(f"  Workflows without key fields: {(final_df['AUDIT_Total_Key_Fields_Count'] == 0).sum()}")
    print(f"  Average key fields per workflow: {final_df['AUDIT_Total_Key_Fields_Count'].mean():.2f}")
    print(f"  Max key fields in a workflow: {final_df['AUDIT_Total_Key_Fields_Count'].max()}")

    # Property usage summary
    print("\n--- Property Usage Summary ---")
    print(f"  Total unique properties referenced: {len(property_df)}")
    print(f"  Key fields (HS + SF): {(property_df['Is_Key_Field'] == True).sum()}")
    print(f"  HubSpot only properties: {((property_df['In_HubSpot_Properties'] == True) & (property_df['In_Salesforce_Mappings'] == False)).sum()}")
    print(f"  Salesforce mapped only: {((property_df['In_HubSpot_Properties'] == False) & (property_df['In_Salesforce_Mappings'] == True)).sum()}")
    print(f"  Unmatched/custom properties: {((property_df['In_HubSpot_Properties'] == False) & (property_df['In_Salesforce_Mappings'] == False)).sum()}")

    # Top referenced properties
    print("\n--- Top 10 Most Referenced Properties ---")
    top_props = property_df.nlargest(10, 'Total_References')
    for _, prop in top_props.iterrows():
        name = prop['HS_Friendly_Name'] if prop['HS_Friendly_Name'] else prop['Internal_Name']
        print(f"  {name} ({prop['Internal_Name']}): {prop['Total_References']} refs [{prop['Classification']}]")

    # Top key fields
    print("\n--- Top 10 Key Fields by Usage ---")
    key_fields_df = property_df[property_df['Is_Key_Field'] == True].nlargest(10, 'Total_References')
    for _, prop in key_fields_df.iterrows():
        print(f"  {prop['HS_Friendly_Name']} ({prop['Internal_Name']}) -> SF:{prop['SF_Field_Name']}: {prop['Total_References']} refs")

    print("\n" + "=" * 60)
    print("AUDIT COMPLETE")
    print("=" * 60)
    print(f"\nOutput files:")
    print(f"  1. {OUTPUT_WORKFLOWS}")
    print(f"  2. {OUTPUT_PROPERTIES}")


if __name__ == "__main__":
    main()
