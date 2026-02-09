"""
READ-ONLY Database Analysis Command
This command ONLY analyzes the database state and reports findings.
It makes ZERO changes - completely safe to run on production.
"""

from django.core.management.base import BaseCommand
from django.db import connection
from django.conf import settings


class Command(BaseCommand):
    help = 'SAFE READ-ONLY analysis of database state vs application requirements'

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.HTTP_INFO('🔍 READ-ONLY Database Analysis')
        )
        self.stdout.write(
            self.style.SUCCESS('This command makes NO CHANGES - completely safe to run')
        )
        
        # Database info
        db_vendor = connection.vendor
        db_name = connection.settings_dict.get('NAME', 'Unknown')
        
        self.stdout.write(f"\nDatabase: {db_vendor}")
        self.stdout.write(f"Database Name: {db_name}")
        
        # Run all analysis
        self.analyze_tables()
        self.analyze_member_table()
        self.analyze_missing_fields()
        self.provide_recommendations()

    def analyze_tables(self):
        """Check which tables exist vs what's expected"""
        self.stdout.write('\n📊 TABLE ANALYSIS')
        self.stdout.write('=' * 70)
        
        expected_tables = {
            'members_app_admin': 'Core - Admin users',
            'members_app_area': 'Core - Areas',
            'members_app_audit': 'Core - Audit trail', 
            'members_app_contact': 'Core - Contacts',
            'members_app_department': 'Core - Departments',
            'members_app_enquiry': 'Core - Enquiries',
            'members_app_enquiryhistory': 'Core - Enquiry history',
            'members_app_jobtype': 'Core - Job types',
            'members_app_member': 'Core - Members',
            'members_app_section': 'Core - Sections',
            'members_app_ward': 'Core - Wards',
            # New tables that might be missing
            'members_app_enquiryattachment': 'NEW - File attachments',
            'members_app_reference_sequence': 'NEW - Reference numbering',
            'members_app_user_mapping': 'NEW - User migration mapping',
        }
        
        with connection.cursor() as cursor:
            for table, description in expected_tables.items():
                if connection.vendor == 'sqlite':
                    cursor.execute("""
                        SELECT COUNT(*) 
                        FROM sqlite_master 
                        WHERE type='table' AND name=%s
                    """, [table])
                else:  # SQL Server
                    cursor.execute("""
                        SELECT COUNT(*) 
                        FROM INFORMATION_SCHEMA.TABLES 
                        WHERE TABLE_NAME = %s
                    """, [table])
                
                exists = cursor.fetchone()[0] > 0
                status = '✅ EXISTS' if exists else '❌ MISSING'
                self.stdout.write(f"{table:35} {status:10} {description}")

    def analyze_member_table(self):
        """Detailed analysis of Member table structure"""
        self.stdout.write('\n👤 MEMBER TABLE ANALYSIS (CRITICAL)')
        self.stdout.write('=' * 70)
        
        with connection.cursor() as cursor:
            # Get all columns in Member table
            if connection.vendor == 'sqlite':
                cursor.execute("PRAGMA table_info(members_app_member)")
                columns = [(row[1], row[2], row[3]) for row in cursor.fetchall()]
            else:  # SQL Server
                cursor.execute("""
                    SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_NAME = 'members_app_member'
                    ORDER BY ORDINAL_POSITION
                """)
                columns = cursor.fetchall()
            
            if not columns:
                self.stdout.write("❌ members_app_member table not found!")
                return
                
            self.stdout.write("Current Member table structure:")
            column_names = []
            for col_name, col_type, nullable in columns:
                column_names.append(col_name)
                null_info = "NULL" if nullable in ('YES', 1) else "NOT NULL"
                self.stdout.write(f"  {col_name:20} {col_type:15} {null_info}")
            
            # Check for old vs new structure
            has_user_field = 'user_id' in column_names
            has_new_fields = all(field in column_names for field in ['first_name', 'last_name', 'email'])
            
            self.stdout.write(f"\n🔍 CRITICAL STRUCTURE ANALYSIS:")
            self.stdout.write(f"  Has user_id (old structure): {'✅ YES' if has_user_field else '❌ NO'}")
            self.stdout.write(f"  Has name/email fields (new):  {'✅ YES' if has_new_fields else '❌ NO'}")
            
            # Determine migration state
            if has_user_field and not has_new_fields:
                state = "OLD_SYSTEM_NEEDS_FULL_MIGRATION"
                description = "Live database in old state - needs complete transformation"
                self.stdout.write(f"  🚨 STATE: {description}")
            elif has_user_field and has_new_fields:
                state = "PARTIAL_MIGRATION_NEEDS_COMPLETION"  
                description = "Partially migrated - needs completion"
                self.stdout.write(f"  ⚠️  STATE: {description}")
            elif not has_user_field and has_new_fields:
                state = "FULLY_MIGRATED"
                description = "Fully migrated - matches dev database"
                self.stdout.write(f"  ✅ STATE: {description}")
            else:
                state = "UNKNOWN_STRUCTURE"
                description = "Unexpected structure - needs investigation"
                self.stdout.write(f"  ❓ STATE: {description}")
            
            # Count members and analyze data
            try:
                cursor.execute("SELECT COUNT(*) FROM members_app_member")
                total_members = cursor.fetchone()[0]
                self.stdout.write(f"\n📊 DATA ANALYSIS:")
                self.stdout.write(f"  Total Members: {total_members}")
                
                if has_user_field:
                    cursor.execute("SELECT COUNT(*) FROM members_app_member WHERE user_id IS NOT NULL")
                    with_user = cursor.fetchone()[0]
                    self.stdout.write(f"  Members with user_id: {with_user}")
                
                if has_new_fields:
                    cursor.execute("""
                        SELECT COUNT(*) FROM members_app_member 
                        WHERE first_name IS NOT NULL AND first_name != ''
                        AND last_name IS NOT NULL AND last_name != ''
                        AND email IS NOT NULL AND email != ''
                    """)
                    populated = cursor.fetchone()[0]
                    self.stdout.write(f"  Members with populated fields: {populated}")
                    
            except Exception as e:
                self.stdout.write(f"  ❌ Could not analyze member data: {e}")

    def analyze_missing_fields(self):
        """Check for missing fields in existing tables"""
        self.stdout.write('\n🔍 MISSING FIELDS ANALYSIS')
        self.stdout.write('=' * 70)
        
        fields_to_check = [
            ('members_app_contact', 'email', 'Contact email addresses'),
        ]
        
        with connection.cursor() as cursor:
            for table, field, description in fields_to_check:
                # Check if table exists first
                if connection.vendor == 'sqlite':
                    cursor.execute("""
                        SELECT COUNT(*) 
                        FROM sqlite_master 
                        WHERE type='table' AND name=%s
                    """, [table])
                else:
                    cursor.execute("""
                        SELECT COUNT(*) 
                        FROM INFORMATION_SCHEMA.TABLES 
                        WHERE TABLE_NAME = %s
                    """, [table])
                
                table_exists = cursor.fetchone()[0] > 0
                if not table_exists:
                    self.stdout.write(f"{table}.{field:15} ❌ TABLE MISSING")
                    continue
                
                # Check if field exists
                if connection.vendor == 'sqlite':
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = [row[1] for row in cursor.fetchall()]
                    field_exists = field in columns
                else:
                    cursor.execute("""
                        SELECT COUNT(*) 
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_NAME = %s AND COLUMN_NAME = %s
                    """, [table, field])
                    field_exists = cursor.fetchone()[0] > 0
                
                status = '✅ EXISTS' if field_exists else '❌ MISSING'
                self.stdout.write(f"{table}.{field:15} {status:10} {description}")

    def provide_recommendations(self):
        """Provide specific recommendations based on findings"""
        self.stdout.write('\n💡 MIGRATION RECOMMENDATIONS')
        self.stdout.write('=' * 70)
        
        self.stdout.write("Based on this analysis, your next steps should be:")
        self.stdout.write("")
        self.stdout.write("1. 🚨 BACKUP DATABASE FIRST (Critical!)")
        self.stdout.write("")
        self.stdout.write("2. Copy these files to your live server:")
        self.stdout.write("   • application/migrations/9999_safe_live_migration.py")
        self.stdout.write("")
        self.stdout.write("3. For data synchronization FROM LIVE TO local/test:")
        self.stdout.write("   ⚠️  Note: sync_live_database.py is now obsolete")
        self.stdout.write("   Use: python manage.py sync_from_live --dry-run")
        self.stdout.write("   Use: python manage.py sync_from_live  # Full sync")
        self.stdout.write("   Use: python manage.py sync_from_live --incremental  # Fast updates")
        self.stdout.write("")
        self.stdout.write("4. The sync command will automatically:")
        self.stdout.write("   • Read data FROM your LIVE database (read-only)")
        self.stdout.write("   • Sync members, enquiries, history, and lookup data")
        self.stdout.write("   • Handle incremental updates without wiping tables")
        self.stdout.write("   • Extract embedded images from descriptions")
        self.stdout.write("")
        self.stdout.write("5. Verify the results and test your application")
        self.stdout.write("")
        self.stdout.write("⚠️  CRITICAL NOTES:")
        self.stdout.write("• This analysis shows your CURRENT database state")
        self.stdout.write("• The sync tool is designed for your exact scenario")  
        self.stdout.write("• It handles the complete application replacement migration")
        self.stdout.write("• Copy these results to share for final verification")
        self.stdout.write("")
        self.stdout.write("✅ ANALYSIS COMPLETE - NO CHANGES MADE TO YOUR DATABASE")
        self.stdout.write("=" * 70)