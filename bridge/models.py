from django.db import models
from django.contrib.auth import get_user_model
import uuid
from bridge.fields import S3Field
from bridge.datalayer import Datalayer
from django.conf import settings

# Create your models here.
from bridge.repo import selectors as rselectors
from typing import List
from authentikate.models import Client, Organization


class Repo(models.Model):
    name = models.CharField(max_length=400)
    creator = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="repos", null=True, blank=True)

    def __str__(self) -> str:
        return self.name


class GithubRepo(Repo):
    repo = models.CharField(max_length=4000)
    user = models.CharField(max_length=4000)
    branch = models.CharField(max_length=4000)

    def __str__(self) -> str:
        return f"{self.user}/{self.repo}:{self.branch}"

    @property
    def pyproject_url(self) -> str:
        return f"https://raw.githubusercontent.com/{self.user}/{self.repo}/{self.branch}/pyproject.toml"

    @property
    def readme_url(self) -> str:
        return f"https://raw.githubusercontent.com/{self.user}/{self.repo}/{self.branch}/README.md"

    @property
    def manifest_url(self) -> str:
        return f"https://raw.githubusercontent.com/{self.user}/{self.repo}/{self.branch}/.arkitekt-next/manifest.yaml"

    @property
    def kabinet_url(self) -> str:
        return self.build_kabinet_url(self.user, self.repo, self.branch)

    @classmethod
    def build_kabinet_url(cls, user: str, repo: str, branch: str) -> str:
        return f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/.arkitekt_next/deployments.yaml"

    class Config:
        constraints = [models.UniqueConstraint(fields=["repo", "user", "branch"], name="Unique repo for url")]


class App(models.Model):
    identifier = models.CharField(max_length=4000)


class S3Store(models.Model):
    path = S3Field(null=True, blank=True, help_text="The store of the image", unique=True)
    key = models.CharField(max_length=1000)
    bucket = models.CharField(max_length=1000)
    populated = models.BooleanField(default=False)


class MediaStore(S3Store):
    def get_presigned_url(self, info, datalayer: Datalayer, host: str | None = None) -> str:
        cache_key = f"presigned_url:{self.bucket}:{self.key}:{host}"
        # Check if the URL is in the cache
        url = cache.get(cache_key)

        if not url:
            # Generate a new presigned URL if not cached
            s3 = datalayer.s3
            url = s3.generate_presigned_url(
                ClientMethod="get_object",
                Params={
                    "Bucket": self.bucket,
                    "Key": self.key,
                },
                ExpiresIn=3600,
            )
            # Replace the endpoint URL
            url = url.replace(settings.AWS_S3_ENDPOINT_URL, host or "")
            # Cache the URL with a timeout of 3600 seconds (same as ExpiresIn)
            cache.set(cache_key, url, timeout=3600)

        return url

    def put_file(self, datalayer: Datalayer, file: str):
        s3 = datalayer.s3
        s3.upload_fileobj(file, self.bucket, self.key)
        self.save()


class Release(models.Model):
    app = models.ForeignKey(App, on_delete=models.CASCADE, related_name="releases")
    version = models.CharField(max_length=400)
    scopes = models.JSONField(default=list)
    logo = models.ForeignKey(MediaStore, on_delete=models.CASCADE, related_name="releases", null=True, blank=True)
    original_logo = models.CharField(max_length=1000, null=True, blank=True, help_text="The original logo url")
    entrypoint = models.CharField(max_length=4000, default="app")
    released_at = models.DateTimeField(auto_now_add=True, help_text="When this release was created")
    created_at = models.DateTimeField(auto_now=True, help_text="When this release was created")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["app", "version"], name="Unique release for version")]


class DockerImage(models.Model):
    image_string = models.CharField(max_length=4000)
    build_at = models.DateTimeField(null=True, blank=True)


class Flavour(models.Model):
    release = models.ForeignKey(Release, on_delete=models.CASCADE, related_name="flavours")
    name = models.CharField(max_length=400)
    deployment_id = models.CharField(max_length=400, unique=True, default=uuid.uuid4)
    flavour = models.CharField(max_length=400, default="vanilla")
    selectors = models.JSONField(default=list)
    repo = models.ForeignKey(Repo, on_delete=models.CASCADE, related_name="flavours")
    image = models.ForeignKey(DockerImage, on_delete=models.CASCADE, related_name="flavours")
    builder = models.CharField(max_length=400)
    inspection = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now=True)
    deployed_at = models.DateTimeField(null=True)
    manifest = models.JSONField(default=dict)
    requirements = models.JSONField(default=dict)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["release", "name"], name="Unique flavour for release")]
        ordering = ["-created_at"]

    def get_selectors(self) -> List[rselectors.Selector]:
        field_json = rselectors.SelectorFieldJson(**{"selectors": self.selectors})
        return field_json.selectors


class Collection(models.Model):
    name = models.CharField(max_length=1000, unique=True, help_text="The name of this Collection")
    description = models.TextField(help_text="A description for the Collection")
    defined_at = models.DateTimeField(auto_created=True, auto_now_add=True)


class Protocol(models.Model):
    name = models.CharField(max_length=1000, unique=True, help_text="The name of this Protocol")
    description = models.TextField(help_text="A description for the Protocol")

    def __str__(self) -> str:
        return self.name


class Definition(models.Model):
    """Actions are abstraction of RPC Tasks. They provide a common API to deal with creating tasks.

    See online Documentation"""

    flavours = models.ManyToManyField(
        Flavour,
        related_name="definitions",
        help_text="The flavours this Definition belongs to",
    )
    definition_version = models.CharField(
        max_length=1000,
        help_text="The version of the Action definition",
        default="0.0.1",
    )

    hash = models.CharField(
        max_length=1000,
        help_text="The hash of the Action (completely unique)",
        unique=True,
    )

    collections = models.ManyToManyField(
        Collection,
        related_name="actions",
        help_text="The collections this Action belongs to",
    )
    pure = models.BooleanField(default=False, help_text="Is this function pure. e.g can we cache the result?")
    idempotent = models.BooleanField(default=False, help_text="Is this function pure. e.g can we cache the result?")
    kind = models.CharField(
        max_length=1000,
        help_text="The kind of this Action. e.g. is it a function or a generator?",
    )
    interfaces = models.JSONField(default=list, help_text="Intercae that we use to interpret the meta data")
    port_groups = models.JSONField(default=list, help_text="Intercae that we use to interpret the meta data")
    name = models.CharField(max_length=1000, help_text="The cleartext name of this Action")
    meta = models.JSONField(null=True, blank=True, help_text="Meta data about this Action")

    description = models.TextField(help_text="A description for the Action")
    scope = models.CharField(
        max_length=1000,
        default="GLOBAL",
        help_text="The scope of this Action. e.g. does the data it needs or produce live only in the scope of this Action or is it global or does it bridge data?",
    )
    is_test_for = models.ManyToManyField(
        "self",
        related_name="tests",
        blank=True,
        symmetrical=False,
        help_text="The users that have pinned the position",
    )
    protocols = models.ManyToManyField(
        Protocol,
        related_name="actions",
        blank=True,
        help_text="The protocols this Action implements (e.g. Predicate)",
    )

    hash = models.CharField(
        max_length=1000,
        help_text="The hash of the Action (completely unique)",
        unique=True,
    )
    defined_at = models.DateTimeField(auto_created=True, auto_now_add=True)

    args = models.JSONField(default=list, help_text="Inputs for this Action")
    returns = models.JSONField(default=list, help_text="Outputs for this Action")

    def __str__(self) -> str:
        return f"{self.name}"


class Backend(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    instance_id = models.CharField(max_length=1000)
    last_heartbeat = models.DateTimeField(auto_now=True)
    kind = models.CharField(max_length=1000, default="unknown")
    name = models.CharField(max_length=1000, default="unset")


class Deployment(models.Model):
    flavour = models.ForeignKey(
        Flavour,
        on_delete=models.CASCADE,
        related_name="deployments",
    )
    backend = models.ForeignKey(Backend, on_delete=models.CASCADE)
    pulled = models.BooleanField(default=False)
    secret_params = models.JSONField(default=dict)
    untyped_params = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now=True)
    local_id = models.CharField(max_length=2000, default="unset")


class Resource(models.Model):
    backend = models.ForeignKey(Backend, on_delete=models.CASCADE, related_name="resources")
    resource_id = models.CharField(max_length=1000)
    name = models.CharField(max_length=1000, default="unset")
    qualifiers = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["backend", "resource_id"], name="Unique resource for backend ")]


class Pod(models.Model):
    backend = models.ForeignKey(Backend, on_delete=models.CASCADE, related_name="pods")
    resource = models.ForeignKey(Resource, on_delete=models.SET_NULL, related_name="pods", null=True, blank=True)
    pod_id = models.CharField(max_length=1000)
    client_id = models.CharField(max_length=1000, null=True, blank=True)
    deployment = models.ForeignKey(
        Deployment,
        on_delete=models.CASCADE,
        related_name="pods",
    )
    status = models.CharField(max_length=1000, default="PENDING")

    created_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["backend", "pod_id"], name="Unique pod for backend ")]
        ordering = ["-created_at"]

    def latest_log_dump(self):
        return self.log_dumps.order_by("-created_at").first()


class LogDump(models.Model):
    pod = models.ForeignKey(
        Pod,
        on_delete=models.CASCADE,
        related_name="log_dumps",
    )
    logs = models.TextField()
    created_at = models.DateTimeField(auto_now=True)


from .signals import *
