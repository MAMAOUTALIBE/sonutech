from django.db import models
from . import defaults

class Content(models.Model):
    title = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    description = models.CharField(max_length=500)
    body = models.TextField(blank=True)
    image = models.CharField(max_length=500, blank=True)
    image_alt = models.CharField(max_length=250, blank=True)
    seo_title = models.CharField(max_length=180, blank=True)
    seo_description = models.CharField(max_length=300, blank=True)
    order = models.PositiveIntegerField(default=0)
    published = models.BooleanField(default=False, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True
        ordering = ['order', 'id']

class Service(Content):
    icon = models.CharField(max_length=40, blank=True)
    needs = models.JSONField(default=list)
    prestations = models.JSONField(default=list)
    benefits = models.JSONField(default=list)

class Slide(Content):
    accent = models.CharField(max_length=180, blank=True)
    primary_label = models.CharField(max_length=100)
    primary_href = models.CharField(max_length=250)
    secondary_label = models.CharField(max_length=100, blank=True)
    secondary_href = models.CharField(max_length=250, blank=True)

class Sector(Content):
    prestations = models.JSONField(default=list)
    benefits = models.JSONField(default=list)

class Course(Content):
    category = models.CharField(max_length=80)
    objectives = models.JSONField(default=list)
    audience = models.JSONField(default=list)
    prerequisites = models.JSONField(default=list)
    program = models.JSONField(default=list)
    duration = models.CharField(max_length=100)
    modality = models.CharField(max_length=150)

class SiteSettings(models.Model):
    site_name = models.CharField(max_length=100, default='SONUTECH')
    tagline = models.CharField(max_length=300, default='Technologie, conseil et solutions durables pour accompagner les entreprises dans leur transformation numérique.')
    about_title = models.CharField(max_length=180, default='La technologie au service de vos idées.')
    about_description = models.CharField(max_length=500, default='SONUTECH accompagne les entreprises dans leur transformation numérique et leurs projets de transition énergétique.')
    about_body = models.JSONField(default=defaults.about_body)
    about_values = models.JSONField(default=defaults.about_values)
    method_steps = models.JSONField(default=defaults.method_steps)
    hero_note = models.CharField(max_length=300, blank=True, default='Un accompagnement sur mesure, de l’idée à la mise en œuvre.')
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    address = models.TextField(blank=True)
    legal_text = models.TextField(blank=True)
    privacy_text = models.TextField(blank=True)
    social_links = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)
    def save(self, *args, **kwargs):
        self.pk = 1
        return super().save(*args, **kwargs)

class ImageAsset(models.Model):
    file = models.ImageField(upload_to='images/%Y/%m/')
    alt = models.CharField(max_length=250)
    created_at = models.DateTimeField(auto_now_add=True)
