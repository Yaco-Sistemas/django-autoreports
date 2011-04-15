# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Deleting field 'Report.report_filter_fields'
        db.delete_column('autoreports_report', 'report_filter_fields')

        # Deleting field 'Report.advanced_options'
        db.delete_column('autoreports_report', 'advanced_options')

        # Deleting field 'Report.report_display_fields'
        db.delete_column('autoreports_report', 'report_display_fields')

        # Adding field 'Report.options'
        db.add_column('autoreports_report', 'options', self.gf('configfield.dbfields.JSONField')(null=True, blank=True), keep_default=False)


    def backwards(self, orm):
        
        # Adding field 'Report.report_filter_fields'
        db.add_column('autoreports_report', 'report_filter_fields', self.gf('django.db.models.fields.TextField')(null=True, blank=True), keep_default=False)

        # Adding field 'Report.advanced_options'
        db.add_column('autoreports_report', 'advanced_options', self.gf('django.db.models.fields.TextField')(null=True, blank=True), keep_default=False)

        # Adding field 'Report.report_display_fields'
        db.add_column('autoreports_report', 'report_display_fields', self.gf('django.db.models.fields.TextField')(null=True, blank=True), keep_default=False)

        # Deleting field 'Report.options'
        db.delete_column('autoreports_report', 'options')


    models = {
        'autoreports.report': {
            'Meta': {'object_name': 'Report'},
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'options': ('configfield.dbfields.JSONField', [], {'null': 'True', 'blank': 'True'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        }
    }

    complete_apps = ['autoreports']
