from django.db import models
from django.contrib.auth import get_user_model
from .storages import PrivateMediaStorage
import uuid
# Create your models here.



class Repo(models.Model):
    name = models.CharField(max_length=400)
    creator = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name
    


class GithubRepo(Repo):
    repo = models.CharField(max_length=4000)
    user = models.CharField(max_length=4000)
    branch = models.CharField(max_length=4000)

    def __str__(self) -> str:
        return f"{self.user}/{self.repo}:{self.branch}"

    @property
    def pyproject_url(self):
        return f"https://raw.githubusercontent.com/{self.user}/{self.repo}/{self.branch}/pyproject.toml"

    @property
    def readme_url(self):
        return f"https://raw.githubusercontent.com/{self.user}/{self.repo}/{self.branch}/README.md"

    @property
    def manifest_url(self):
        return f"https://raw.githubusercontent.com/{self.user}/{self.repo}/{self.branch}/.arkitekt/manifest.yaml"

    @property
    def deployments_url(self):
        return f"https://raw.githubusercontent.com/{self.user}/{self.repo}/{self.branch}/.arkitekt/deployments.yaml"
    
    
    

class App(models.Model):
    identifier = models.CharField(max_length=4000)


class Release(models.Model):
    app = models.ForeignKey(App, on_delete=models.CASCADE, related_name="releases")
    version = models.CharField(max_length=400)
    scopes = models.JSONField(default=list)
    logo = models.ImageField(
        max_length=1000, null=True, blank=True, storage=PrivateMediaStorage()
    )
    original_logo = models.CharField(
        max_length=1000, null=True, blank=True, help_text="The original logo url"
    )
    entrypoint = models.CharField(max_length=4000, default="app")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["app", "version"], name="Unique release for version"
            )
        ]


class Flavour(models.Model):
    release = models.ForeignKey(
        Release, on_delete=models.CASCADE, related_name="flavours"
    )
    name = models.CharField(max_length=400)
    deployment_id = models.CharField(max_length=400, unique=True, default=uuid.uuid4)
    build_id = models.CharField(max_length=400, default=uuid.uuid4)
    flavour = models.CharField(max_length=400, default="vanilla")
    selectors = models.JSONField(default=list)
    repo = models.ForeignKey(
        Repo, on_delete=models.CASCADE, related_name="flavours"
    )
    image = models.CharField(max_length=400, default="jhnnsrs/fake:latest")
    builder = models.CharField(max_length=400)
    definitions = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now=True)
    deployed_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["release", "name"], name="Unique flavour for release"
            )
        ]
        ordering = ["-created_at"]


class Whale(models.Model):
    flavour = models.ForeignKey(
        Flavour,
        on_delete=models.CASCADE,
        related_name="whales",
    )
    url = models.CharField(max_length=1000)
    client_id = models.CharField(max_length=1000)
    token = models.CharField(max_length=10000, null=True)
    creator = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now=True)
