from typing import Any, Optional
from rekuest_core import enums
from pydantic import BaseModel, Field, model_validator
from typing_extensions import Self


class BindsInputModel(BaseModel):
    implementations: Optional[list[str]]
    clients: Optional[list[str]]
    desired_instances: int = 1
    minimum_instances: int = 1


class EffectDependencyInputModel(BaseModel):
    key: str
    condition: str
    value: str


class EffectInputModel(BaseModel):
    function: str
    dependencies: list[str] | None = []
    message: str | None = None
    kind: enums.EffectKind
    hook: str | None
    ward: str | None


class ChoiceInputModel(BaseModel):
    value: str
    label: str
    image: str | None = None
    description: str | None = None


class ValidatorInputModel(BaseModel):
    function: str
    dependencies: list[str] | None = []
    label: str | None = None
    error_message: str | None = None


class AssignWidgetInputModel(BaseModel):
    kind: enums.AssignWidgetKind
    query: str | None = None
    choices: list[ChoiceInputModel] | None = None
    state_choices: str | None = None
    follow_value: str | None = None
    min: float | None = None
    max: float | None = None
    step: float | None = None
    placeholder: str | None = None
    hook: str | None = None
    ward: str | None = None
    fallback: Optional["AssignWidgetInputModel"] = None
    filters: list["PortInputModel"] | None =  None
    dependencies: list[str] | None = [] 


class ReturnWidgetInputModel(BaseModel):
    kind: enums.ReturnWidgetKind
    query: str | None = None
    choices: list[ChoiceInputModel] | None = None
    min: int | None = None
    max: int | None = None
    step: int | None = None
    placeholder: str | None = None
    hook: str | None = None
    ward: str | None = None


class PortInputModel(BaseModel):
    validators: list[ValidatorInputModel] | None = None
    key: str
    label: str | None = None
    kind: enums.PortKind
    description: str | None = None
    identifier: str | None = None
    nullable: bool = False
    effects: list[EffectInputModel] | None = None
    default: Any | None = None
    children: list["PortInputModel"] | None = None
    choices: list[ChoiceInputModel] | None = None
    assign_widget: Optional["AssignWidgetInputModel"] = None
    return_widget: Optional["ReturnWidgetInputModel"] = None

    @model_validator(mode="after")
    def check_children_for_port(cls, self) -> Self:

        if self.kind == enums.PortKind.LIST and (self.children is None or len(self.children) != 1):
            raise ValueError("Port of kind LIST must have exactly on children")
        return self


class PortGroupInputModel(BaseModel):
    key: str
    title: str | None
    description: str | None
    effects: list[EffectInputModel] | None
    ports: list[str]


class DefinitionInputModel(BaseModel):
    """A definition for a implementation"""

    description: str = "No description provided"
    collections: list[str] = Field(default_factory=list)
    name: str
    stateful: bool = False
    port_groups: list[PortGroupInputModel] = Field(default_factory=list)
    args: list[PortInputModel] = Field(default_factory=list)
    returns: list[PortInputModel] = Field(default_factory=list)
    kind: enums.ActionKind
    is_test_for: list["str"] = Field(default_factory=list)
    interfaces: list[str] = Field(default_factory=list)
    is_dev: bool = False
    logo: str | None = None


class DependencyInputModel(BaseModel):
    action: str
    hash: str
    reference: str | None
    binds: BindsInputModel | None
    optional: bool = False
    viable_instances: int | None


class ImplementationInputModel(BaseModel):
    definition: DefinitionInputModel
    dependencies: list[DependencyInputModel]
    interface: str
    params: dict[str, Any] | None = None
    instance_id: str | None = None
    dynamic: bool = False
    logo: str | None = None


AssignWidgetInputModel.model_rebuild()
