from django.db import models

# Create your models here.

class Member(models.Model):
    memberid = models.CharField(primary_key=True, max_length=50)
    memberpw = models.CharField(max_length=50)

    def __str__(self):
        return "Member ID: %s" % self.memberid

class Case(models.Model):
    caseid = models.AutoField(primary_key=True)
    doclink = models.CharField(max_length=300, blank=True, null=True)
    hash = models.CharField(max_length=300)
    qrlink = models.CharField(max_length=300)

    def __str__(self):
        return "%d" % self.caseid

class Membercase(models.Model):
    membercaseid = models.AutoField(primary_key=True)
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    case = models.ForeignKey(Case, on_delete=models.CASCADE)

    class Meta:
        unique_together = ['member', 'case']

# def case_directory_path(instance, filename):
   # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
#    return 'videos/{0}/{1}'.format(instance.case.caseid, filename)

class Video(models.Model):
    upload = models.FileField(upload_to=case_directory_path)
    case = models.ForeignKey(Case, on_delete=models.DO_NOTHING)
    videoid = models.AutoField(primary_key=True)
    videolink = models.CharField(max_length=300)
    name = models.CharField(max_length=50)
    contact = models.CharField(max_length=100)
    email = models.EmailField(max_length=254, null=True)

    class Meta:
        unique_together = ['case', 'videoid']
    
    def __str__(self):
        return "Case %d Video %d" % ( self.case.caseid, self.videoid )
    
class Mark(models.Model):
    markid = models.AutoField(primary_key=True)
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    video = models.ForeignKey(Video, on_delete=models.CASCADE)

    class Meta:
        unique_together = ['member', 'video']


