# encoding: utf-8
from south.db import db
from south.v2 import SchemaMigration


class Migration(SchemaMigration):

    def forwards(self, orm):

        # Adding model 'Report'
        db.create_table('autoreports_report', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=200)),
            ('report_filter_fields', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('report_display_fields', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('advanced_options', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('content_type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['contenttypes.ContentType'])),
        ))
        db.send_create_signal('autoreports', ['Report'])

    def backwards(self, orm):

        # Deleting model 'Report'
        db.delete_table('autoreports_report')

    models = {
        'autoreports.report': {
            'Meta': {'object_name': 'Report'},
            'advanced_options': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'report_display_fields': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'report_filter_fields': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
        }
    }

    complete_apps = ['autoreports']
