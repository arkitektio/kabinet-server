from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from authentikate.models import Organization
from django.conf import settings
from bridge.mutations.repo import _create_github_repo
from bridge import inputs
from asgiref.sync import async_to_sync
from pydantic import BaseModel


class RepoMap(BaseModel):
    organization: str
    repos: list[str]

class RepoMapSettings(BaseModel):
    repo_map: list[RepoMap]


async def create_github_repos(repo_map: list[RepoMap]):

    for repo in repo_map:
        
        organization, _  = await Organization.objects.aget_or_create(slug=repo.organization)
        
        for repo_identifier in repo.repos:
            input = inputs.CreateGithubRepoInput(
                identifier=repo_identifier, name=repo_identifier
            )
            
            try:
                await _create_github_repo(input, organization, None)
            except Exception as e:
                raise e
                
                print(f"Error creating repo {repo_identifier}: {e}")
        


class Command(BaseCommand):
    help = "Ensures that the repos are used"

    def handle(self, *args, **kwargs):
        
        
        repos = settings.REPO_MAP
        match = RepoMapSettings(repo_map=repos)
        repos = match.repo_map

        async_to_sync(create_github_repos)(repos)
