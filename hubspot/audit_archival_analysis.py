#!/usr/bin/env python3
"""
HubSpot Audit - Archival Analysis
Cross-references workflows and properties to identify:
1. Old workflows (created before 2025) and their criticality
2. Properties that can be archived (only used by disabled/deletable workflows)
3. Critical properties that must NOT be archived
4. Dependency chains that block archival
"""

import pandas as pd
import os
from datetime import datetime
from collections import defaultdict

# File paths
BASE_DIR = "/home/user/rho-audit/hubspot"
WORKFLOWS_FILE = os.path.join(BASE_DIR, "audit_consolidated_workflows.csv")
PROPERTIES_FILE = os.path.join(BASE_DIR, "audit_property_usage.csv")
OUTPUT_WORKFLOW_ANALYSIS = os.path.join(BASE_DIR, "audit_archival_workflows.csv")
OUTPUT_PROPERTY_ANALYSIS = os.path.join(BASE_DIR, "audit_archival_properties.csv")
OUTPUT_SUMMARY = os.path.join(BASE_DIR, "audit_archival_summary.csv")

# Date threshold for "old" workflows
CUTOFF_DATE = datetime(2025, 1, 1)


def parse_date(date_str):
    """Parse various date formats"""
    if pd.isna(date_str) or date_str == '' or date_str == 'NaT':
        return None
    try:
        # Try common formats
        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%m/%d/%y %I:%M %p']:
            try:
                return datetime.strptime(str(date_str), fmt)
            except ValueError:
                continue
        return None
    except Exception:
        return None


def load_data():
    """Load workflow and property data"""
    print("Loading data...")
    workflows_df = pd.read_csv(WORKFLOWS_FILE)
    properties_df = pd.read_csv(PROPERTIES_FILE)
    print(f"  Loaded {len(workflows_df)} workflows")
    print(f"  Loaded {len(properties_df)} properties")
    return workflows_df, properties_df


def analyze_workflows(workflows_df):
    """Analyze workflows for archival potential"""
    print("\nAnalyzing workflows...")

    results = []

    for _, row in workflows_df.iterrows():
        flow_id = row['FlowId']
        name = row['Name']

        # Parse dates
        created_on = parse_date(row.get('XLSX_Created_On', ''))
        updated_on = parse_date(row.get('XLSX_Updated_On', ''))

        # Determine if old workflow
        is_old = created_on is not None and created_on < CUTOFF_DATE

        # Get status info
        is_enabled = row.get('XLSX_On_Or_Off', False) == True
        recommended_action = str(row.get('Recommended Action', ''))
        is_delete_recommended = 'Delete' in recommended_action
        is_consolidate_recommended = 'Consolidate' in recommended_action

        # Get enrollment data
        enrolled_total = row.get('XLSX_Enrolled_Total', 0)
        enrolled_last_7_days = row.get('XLSX_Enrolled_Last_7_Days', 0)
        currently_enrolled = row.get('XLSX_Currently_Enrolled', 0)

        # Handle NaN values
        enrolled_total = 0 if pd.isna(enrolled_total) else enrolled_total
        enrolled_last_7_days = 0 if pd.isna(enrolled_last_7_days) else enrolled_last_7_days
        currently_enrolled = 0 if pd.isna(currently_enrolled) else currently_enrolled

        # Get property counts
        key_fields_count = row.get('AUDIT_Total_Key_Fields_Count', 0)
        uses_sf_props = row.get('AUDIT_Uses_SF_Connected_Props', False)
        writes_props = str(row.get('Writes Properties', ''))
        reads_props = str(row.get('Reads Properties', ''))

        # Count properties
        writes_count = len([p for p in writes_props.split(',') if p.strip()]) if writes_props else 0
        reads_count = len([p for p in reads_props.split(',') if p.strip()]) if reads_props else 0

        # Determine archival eligibility
        # Cannot archive if: enabled, has recent activity, uses SF-connected props, or is canonical
        is_canonical = 'Canonical' in recommended_action
        has_recent_activity = enrolled_last_7_days > 0 or currently_enrolled > 0

        can_archive = (
            not is_enabled and
            not has_recent_activity and
            is_delete_recommended
        )

        # Risk assessment
        if uses_sf_props and key_fields_count > 5:
            archival_risk = "HIGH - Heavy SF Integration"
        elif uses_sf_props:
            archival_risk = "MEDIUM - SF Connected"
        elif is_canonical:
            archival_risk = "HIGH - Canonical Workflow"
        elif is_enabled and has_recent_activity:
            archival_risk = "HIGH - Active"
        elif is_enabled:
            archival_risk = "MEDIUM - Enabled"
        elif is_delete_recommended:
            archival_risk = "LOW - Delete Recommended"
        else:
            archival_risk = "MEDIUM - Review Needed"

        # Calculate days since last update
        days_since_update = None
        if updated_on:
            days_since_update = (datetime.now() - updated_on).days

        results.append({
            'FlowId': flow_id,
            'Name': name,

            # Archival Assessment
            'ARCHIVAL_Can_Archive': can_archive,
            'ARCHIVAL_Risk_Level': archival_risk,
            'ARCHIVAL_Blocker': (
                "Active enrollment" if has_recent_activity else
                "Enabled" if is_enabled else
                "Canonical workflow" if is_canonical else
                "None" if can_archive else
                "Review needed"
            ),

            # Age & Activity
            'Is_Old_Workflow': is_old,
            'Created_Date': created_on.strftime('%Y-%m-%d') if created_on else '',
            'Last_Updated': updated_on.strftime('%Y-%m-%d') if updated_on else '',
            'Days_Since_Update': days_since_update,
            'Created_Year': created_on.year if created_on else '',

            # Status
            'Is_Enabled': is_enabled,
            'Recommended_Action': recommended_action,
            'Is_Delete_Recommended': is_delete_recommended,
            'Is_Consolidate_Target': is_consolidate_recommended,
            'Is_Canonical': is_canonical,

            # Activity Metrics
            'Enrolled_Total': enrolled_total,
            'Enrolled_Last_7_Days': enrolled_last_7_days,
            'Currently_Enrolled': currently_enrolled,
            'Has_Recent_Activity': has_recent_activity,

            # Property Impact
            'Uses_SF_Connected_Props': uses_sf_props,
            'Key_Fields_Count': key_fields_count,
            'Writes_Props_Count': writes_count,
            'Reads_Props_Count': reads_count,
            'Total_Props_Touched': writes_count + reads_count,

            # Original property lists for reference
            'Writes_Properties': writes_props,
            'Reads_Properties': reads_props,
            'Key_Fields_Detailed': row.get('AUDIT_Writes_Key_Fields_Detailed', ''),
        })

    return pd.DataFrame(results)


def analyze_properties(properties_df, workflows_df):
    """Analyze properties for archival potential based on workflow usage"""
    print("\nAnalyzing properties for archival eligibility...")

    # Build lookup of workflow status by name
    workflow_status = {}
    for _, row in workflows_df.iterrows():
        name = str(row['Name'])
        workflow_status[name] = {
            'is_enabled': row.get('XLSX_On_Or_Off', False) == True,
            'is_delete_recommended': 'Delete' in str(row.get('Recommended Action', '')),
            'is_old': parse_date(row.get('XLSX_Created_On', '')) is not None and
                      parse_date(row.get('XLSX_Created_On', '')) < CUTOFF_DATE,
            'has_recent_activity': (
                (row.get('XLSX_Enrolled_Last_7_Days', 0) or 0) > 0 or
                (row.get('XLSX_Currently_Enrolled', 0) or 0) > 0
            ),
            'created_date': parse_date(row.get('XLSX_Created_On', '')),
        }

    results = []

    for _, row in properties_df.iterrows():
        internal_name = row['Internal_Name']
        friendly_name = row.get('HS_Friendly_Name', '')
        classification = row['Classification']
        is_key_field = row.get('Is_Key_Field', False)

        # Parse workflow lists
        workflows_writing_str = str(row.get('Workflows_Writing', ''))
        workflows_reading_str = str(row.get('Workflows_Reading', ''))

        workflows_writing = [w.strip() for w in workflows_writing_str.split(';') if w.strip() and w.strip() != '...']
        workflows_reading = [w.strip() for w in workflows_reading_str.split(';') if w.strip() and w.strip() != '...']

        all_workflows = list(set(workflows_writing + workflows_reading))

        # Analyze workflow dependencies
        enabled_workflows = []
        disabled_workflows = []
        delete_recommended_workflows = []
        active_workflows = []
        old_workflows = []

        for wf_name in all_workflows:
            status = workflow_status.get(wf_name, {})
            if status.get('is_enabled'):
                enabled_workflows.append(wf_name)
            else:
                disabled_workflows.append(wf_name)

            if status.get('is_delete_recommended'):
                delete_recommended_workflows.append(wf_name)

            if status.get('has_recent_activity'):
                active_workflows.append(wf_name)

            if status.get('is_old'):
                old_workflows.append(wf_name)

        # Determine archival eligibility
        total_workflows = len(all_workflows)
        all_disabled = len(enabled_workflows) == 0 and total_workflows > 0
        all_delete_recommended = len(delete_recommended_workflows) == total_workflows and total_workflows > 0
        no_active_usage = len(active_workflows) == 0

        # Can archive property if:
        # 1. No workflows use it, OR
        # 2. All workflows using it are disabled AND delete-recommended AND no recent activity
        can_archive = (
            total_workflows == 0 or
            (all_disabled and all_delete_recommended and no_active_usage)
        )

        # Criticality assessment
        if is_key_field and len(enabled_workflows) > 3:
            criticality = "CRITICAL - Key Field, Multiple Active Workflows"
        elif is_key_field and len(enabled_workflows) > 0:
            criticality = "HIGH - Key Field, Active Usage"
        elif is_key_field:
            criticality = "MEDIUM - Key Field, No Active Workflows"
        elif len(enabled_workflows) > 5:
            criticality = "HIGH - Heavy Workflow Usage"
        elif len(enabled_workflows) > 0:
            criticality = "MEDIUM - Active Workflow Usage"
        elif total_workflows > 0:
            criticality = "LOW - Only Disabled Workflows"
        else:
            criticality = "NONE - Unused in Workflows"

        # Archival blocker
        if len(active_workflows) > 0:
            blocker = f"Active workflows: {', '.join(active_workflows[:3])}" + ("..." if len(active_workflows) > 3 else "")
        elif len(enabled_workflows) > 0:
            blocker = f"Enabled workflows: {', '.join(enabled_workflows[:3])}" + ("..." if len(enabled_workflows) > 3 else "")
        elif is_key_field and not can_archive:
            blocker = "Key field - review SF sync impact"
        elif can_archive:
            blocker = "None - Can Archive"
        else:
            blocker = "Review workflow dependencies"

        results.append({
            'Internal_Name': internal_name,
            'HS_Friendly_Name': friendly_name,
            'Classification': classification,

            # Archival Assessment
            'ARCHIVAL_Can_Archive': can_archive,
            'ARCHIVAL_Criticality': criticality,
            'ARCHIVAL_Blocker': blocker,

            # Key Field Status
            'Is_Key_Field': is_key_field,
            'SF_Field_Name': row.get('SF_Field_Name', ''),
            'SF_Sync_Rule': row.get('SF_Sync_Rule', ''),

            # Usage Metrics
            'Total_Workflow_References': row.get('Total_References', 0),
            'Workflows_Writing_Count': row.get('Total_Workflows_Writing', 0),
            'Workflows_Reading_Count': row.get('Total_Workflows_Reading', 0),

            # Dependency Analysis
            'Total_Workflows_Using': total_workflows,
            'Enabled_Workflows_Count': len(enabled_workflows),
            'Disabled_Workflows_Count': len(disabled_workflows),
            'Delete_Recommended_Workflows_Count': len(delete_recommended_workflows),
            'Active_Workflows_Count': len(active_workflows),
            'Old_Workflows_Count': len(old_workflows),

            # Status Flags
            'All_Workflows_Disabled': all_disabled,
            'All_Delete_Recommended': all_delete_recommended,
            'No_Active_Usage': no_active_usage,

            # HubSpot Property Details
            'HS_Type': row.get('HS_Type', ''),
            'HS_Group_Name': row.get('HS_Group_Name', ''),
            'HS_Fill_Rate': row.get('HS_Fill_Rate', ''),
            'HS_Last_Updated_Time': row.get('HS_Last_Updated_Time', ''),
            'HS_HubSpot_Defined': row.get('HS_HubSpot_Defined', ''),

            # Workflow Lists (truncated)
            'Enabled_Workflows': '; '.join(enabled_workflows[:10]) + ('...' if len(enabled_workflows) > 10 else ''),
            'Active_Workflows': '; '.join(active_workflows[:10]) + ('...' if len(active_workflows) > 10 else ''),
            'Old_Workflows_Only': '; '.join(old_workflows[:10]) + ('...' if len(old_workflows) > 10 else ''),
        })

    return pd.DataFrame(results)


def generate_summary(workflows_analysis, properties_analysis):
    """Generate summary statistics for archival analysis"""
    print("\nGenerating summary...")

    summary = []

    # Workflow statistics
    total_workflows = len(workflows_analysis)
    old_workflows = workflows_analysis['Is_Old_Workflow'].sum()
    can_archive_workflows = workflows_analysis['ARCHIVAL_Can_Archive'].sum()
    enabled_workflows = workflows_analysis['Is_Enabled'].sum()

    summary.append({'Category': 'WORKFLOWS', 'Metric': 'Total Workflows', 'Value': total_workflows, 'Details': ''})
    summary.append({'Category': 'WORKFLOWS', 'Metric': 'Old Workflows (Pre-2025)', 'Value': old_workflows, 'Details': f'{old_workflows/total_workflows*100:.1f}%'})
    summary.append({'Category': 'WORKFLOWS', 'Metric': 'Can Archive (Safe)', 'Value': can_archive_workflows, 'Details': 'Disabled + Delete Recommended + No Activity'})
    summary.append({'Category': 'WORKFLOWS', 'Metric': 'Currently Enabled', 'Value': enabled_workflows, 'Details': ''})
    summary.append({'Category': 'WORKFLOWS', 'Metric': 'Has Recent Activity', 'Value': workflows_analysis['Has_Recent_Activity'].sum(), 'Details': 'Enrolled in last 7 days or currently enrolled'})

    # Workflow by year
    for year in sorted(workflows_analysis['Created_Year'].dropna().unique()):
        if year:
            count = (workflows_analysis['Created_Year'] == year).sum()
            summary.append({'Category': 'WORKFLOWS_BY_YEAR', 'Metric': f'Created in {int(year)}', 'Value': count, 'Details': ''})

    # Property statistics
    total_props = len(properties_analysis)
    can_archive_props = properties_analysis['ARCHIVAL_Can_Archive'].sum()
    key_fields = properties_analysis['Is_Key_Field'].sum()

    summary.append({'Category': 'PROPERTIES', 'Metric': 'Total Properties Referenced', 'Value': total_props, 'Details': ''})
    summary.append({'Category': 'PROPERTIES', 'Metric': 'Can Archive (Safe)', 'Value': can_archive_props, 'Details': 'No active workflow dependencies'})
    summary.append({'Category': 'PROPERTIES', 'Metric': 'Key Fields (HS + SF)', 'Value': key_fields, 'Details': 'Sync with Salesforce'})
    summary.append({'Category': 'PROPERTIES', 'Metric': 'Used Only by Old Workflows', 'Value': (properties_analysis['Old_Workflows_Count'] == properties_analysis['Total_Workflows_Using']).sum(), 'Details': ''})

    # Risk breakdown
    for risk in ['LOW - Delete Recommended', 'MEDIUM - Review Needed', 'MEDIUM - Enabled', 'MEDIUM - SF Connected', 'HIGH - Active', 'HIGH - Canonical Workflow', 'HIGH - Heavy SF Integration']:
        count = (workflows_analysis['ARCHIVAL_Risk_Level'] == risk).sum()
        if count > 0:
            summary.append({'Category': 'WORKFLOW_RISK', 'Metric': risk, 'Value': count, 'Details': ''})

    # Criticality breakdown
    for crit in properties_analysis['ARCHIVAL_Criticality'].unique():
        count = (properties_analysis['ARCHIVAL_Criticality'] == crit).sum()
        summary.append({'Category': 'PROPERTY_CRITICALITY', 'Metric': crit, 'Value': count, 'Details': ''})

    return pd.DataFrame(summary)


def print_key_findings(workflows_analysis, properties_analysis, summary_df):
    """Print key findings to console"""
    print("\n" + "=" * 70)
    print("KEY FINDINGS - ARCHIVAL ANALYSIS")
    print("=" * 70)

    # Old workflows
    print("\n--- OLD WORKFLOWS (Created Before 2025) ---")
    old_wf = workflows_analysis[workflows_analysis['Is_Old_Workflow'] == True]
    print(f"Total old workflows: {len(old_wf)}")
    print(f"  - Enabled: {old_wf['Is_Enabled'].sum()}")
    print(f"  - Can archive: {old_wf['ARCHIVAL_Can_Archive'].sum()}")
    print(f"  - Using SF-connected props: {old_wf['Uses_SF_Connected_Props'].sum()}")

    # Archival candidates - workflows
    print("\n--- WORKFLOW ARCHIVAL CANDIDATES ---")
    archive_wf = workflows_analysis[workflows_analysis['ARCHIVAL_Can_Archive'] == True].sort_values('Days_Since_Update', ascending=False)
    print(f"Total safe to archive: {len(archive_wf)}")
    if len(archive_wf) > 0:
        print("\nTop 10 oldest archival candidates:")
        for _, row in archive_wf.head(10).iterrows():
            print(f"  - {row['Name'][:60]}...")
            print(f"    Created: {row['Created_Date']} | Last Updated: {row['Last_Updated']} | Total Enrolled: {row['Enrolled_Total']}")

    # Critical workflows (DO NOT ARCHIVE)
    print("\n--- CRITICAL WORKFLOWS (DO NOT ARCHIVE) ---")
    critical_wf = workflows_analysis[
        (workflows_analysis['Is_Enabled'] == True) &
        (workflows_analysis['Has_Recent_Activity'] == True) &
        (workflows_analysis['Uses_SF_Connected_Props'] == True)
    ].sort_values('Key_Fields_Count', ascending=False)
    print(f"Total critical: {len(critical_wf)}")
    if len(critical_wf) > 0:
        print("\nTop 10 most critical (by key fields):")
        for _, row in critical_wf.head(10).iterrows():
            print(f"  - {row['Name'][:60]}...")
            print(f"    Key Fields: {row['Key_Fields_Count']} | Enrolled 7d: {row['Enrolled_Last_7_Days']} | Currently: {row['Currently_Enrolled']}")

    # Archival candidates - properties
    print("\n--- PROPERTY ARCHIVAL CANDIDATES ---")
    archive_props = properties_analysis[properties_analysis['ARCHIVAL_Can_Archive'] == True]
    print(f"Total safe to archive: {len(archive_props)}")
    if len(archive_props) > 0:
        print("\nTop 20 property archival candidates:")
        for _, row in archive_props.head(20).iterrows():
            name = row['HS_Friendly_Name'] if row['HS_Friendly_Name'] else row['Internal_Name']
            print(f"  - {name} ({row['Internal_Name']})")
            print(f"    Classification: {row['Classification']} | Total Refs: {row['Total_Workflow_References']}")

    # Critical properties (DO NOT ARCHIVE)
    print("\n--- CRITICAL PROPERTIES (DO NOT ARCHIVE) ---")
    critical_props = properties_analysis[
        properties_analysis['ARCHIVAL_Criticality'].str.contains('CRITICAL|HIGH')
    ].sort_values('Enabled_Workflows_Count', ascending=False)
    print(f"Total critical/high: {len(critical_props)}")
    if len(critical_props) > 0:
        print("\nTop 15 most critical properties:")
        for _, row in critical_props.head(15).iterrows():
            name = row['HS_Friendly_Name'] if row['HS_Friendly_Name'] else row['Internal_Name']
            print(f"  - {name} ({row['Internal_Name']})")
            print(f"    {row['ARCHIVAL_Criticality']}")
            print(f"    Enabled Workflows: {row['Enabled_Workflows_Count']} | SF Field: {row['SF_Field_Name']}")

    # Old workflows with critical properties
    print("\n--- OLD WORKFLOWS WITH HIGH PROPERTY IMPACT ---")
    old_high_impact = workflows_analysis[
        (workflows_analysis['Is_Old_Workflow'] == True) &
        (workflows_analysis['Is_Enabled'] == True) &
        (workflows_analysis['Key_Fields_Count'] > 3)
    ].sort_values('Key_Fields_Count', ascending=False)
    print(f"Old + Enabled + >3 Key Fields: {len(old_high_impact)}")
    if len(old_high_impact) > 0:
        print("\nThese old workflows have significant SF integration:")
        for _, row in old_high_impact.head(10).iterrows():
            print(f"  - {row['Name'][:60]}...")
            print(f"    Created: {row['Created_Date']} | Key Fields: {row['Key_Fields_Count']} | Enrolled 7d: {row['Enrolled_Last_7_Days']}")


def main():
    print("=" * 70)
    print("HubSpot Audit - Archival Analysis")
    print("=" * 70)
    print(f"Cutoff date for 'old' workflows: {CUTOFF_DATE.strftime('%Y-%m-%d')}")

    # Load data
    workflows_df, properties_df = load_data()

    # Analyze workflows
    workflows_analysis = analyze_workflows(workflows_df)
    workflows_analysis = workflows_analysis.sort_values(
        ['ARCHIVAL_Can_Archive', 'Is_Old_Workflow', 'Days_Since_Update'],
        ascending=[False, False, False]
    )

    # Analyze properties
    properties_analysis = analyze_properties(properties_df, workflows_df)
    properties_analysis = properties_analysis.sort_values(
        ['ARCHIVAL_Can_Archive', 'Is_Key_Field', 'Total_Workflow_References'],
        ascending=[False, False, False]
    )

    # Generate summary
    summary_df = generate_summary(workflows_analysis, properties_analysis)

    # Save outputs
    print("\nSaving outputs...")
    workflows_analysis.to_csv(OUTPUT_WORKFLOW_ANALYSIS, index=False)
    print(f"  Workflow analysis: {OUTPUT_WORKFLOW_ANALYSIS}")

    properties_analysis.to_csv(OUTPUT_PROPERTY_ANALYSIS, index=False)
    print(f"  Property analysis: {OUTPUT_PROPERTY_ANALYSIS}")

    summary_df.to_csv(OUTPUT_SUMMARY, index=False)
    print(f"  Summary: {OUTPUT_SUMMARY}")

    # Print key findings
    print_key_findings(workflows_analysis, properties_analysis, summary_df)

    print("\n" + "=" * 70)
    print("ARCHIVAL ANALYSIS COMPLETE")
    print("=" * 70)
    print(f"\nOutput files:")
    print(f"  1. {OUTPUT_WORKFLOW_ANALYSIS}")
    print(f"  2. {OUTPUT_PROPERTY_ANALYSIS}")
    print(f"  3. {OUTPUT_SUMMARY}")


if __name__ == "__main__":
    main()
