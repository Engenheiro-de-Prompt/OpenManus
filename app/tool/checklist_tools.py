from typing import List, Dict, Any

from app.tool.base import BaseTool, ToolResult
from app.agent.checklist_manager import ChecklistManager
from app.exceptions import ToolError
from app.logger import logger

class ViewChecklistTool(BaseTool):
    name: str = "view_checklist"
    description: str = "Displays all tasks and their current statuses from the main checklist."
    args_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {},
        "required": []
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        logger.info("ViewChecklistTool invoked.")
        try:
            manager = ChecklistManager()
            await manager._load_checklist() # Load tasks explicitly
            tasks = manager.get_tasks()

            if not tasks:
                return ToolResult(output="O checklist está vazio ou não foi encontrado.")

            formatted_tasks = ["Checklist Principal de Tarefas:"]
            for task in tasks:
                formatted_tasks.append(f"- [{task.get('status', 'N/A')}] {task.get('description', 'Sem descrição')}")

            return ToolResult(output="\n".join(formatted_tasks))
        except Exception as e:
            logger.error(f"ViewChecklistTool: Error accessing checklist: {e}")
            raise ToolError(f"Erro ao visualizar checklist: {e}")


class AddChecklistTaskTool(BaseTool):
    name: str = "add_checklist_task"
    description: str = "Adds a new task to the main checklist. Default status is 'Pendente'."
    args_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "task_description": {
                "type": "string",
                "description": "The description of the task to add."
            },
            "status": {
                "type": "string",
                "description": "Optional. The initial status of the task (e.g., Pendente, Em Andamento). Defaults to 'Pendente'.",
                "default": "Pendente",
                "enum": ["Pendente", "Em Andamento", "Concluído", "Bloqueado"]
            }
        },
        "required": ["task_description"]
    }

    async def execute(self, task_description: str, status: str = "Pendente", **kwargs: Any) -> ToolResult:
        logger.info(f"AddChecklistTaskTool invoked with task_description: '{task_description}', status: '{status}'")
        try:
            # Validate status against allowed values (although schema should handle this, good for defense)
            allowed_statuses = self.args_schema["properties"]["status"]["enum"]
            if status not in allowed_statuses:
                raise ToolError(f"Status inválido '{status}'. Status permitidos são: {', '.join(allowed_statuses)}")

            manager = ChecklistManager()
            await manager._load_checklist() # Load tasks explicitly
            success = await manager.add_task(task_description=task_description, status=status)

            if success:
                return ToolResult(output=f"Tarefa '{task_description}' adicionada ao checklist com status '{status}'.")
            else:
                # Check if task exists to provide a more specific message
                existing_task = manager.get_task_by_description(task_description)
                if existing_task:
                    return ToolResult(output=f"Falha ao adicionar tarefa '{task_description}'. Tarefa já existe com status '{existing_task['status']}'.")
                return ToolResult(output=f"Falha ao adicionar tarefa '{task_description}'. Consulte os logs para mais detalhes.")
        except ToolError as te:
            logger.error(f"AddChecklistTaskTool: ToolError adding task: {te}")
            raise te # Re-raise ToolError
        except Exception as e:
            logger.error(f"AddChecklistTaskTool: Unexpected error adding task: {e}")
            raise ToolError(f"Erro inesperado ao adicionar tarefa ao checklist: {e}")


class UpdateChecklistTaskTool(BaseTool):
    name: str = "update_checklist_task"
    description: str = "Updates the status of an existing task in the main checklist."
    args_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "task_description": {
                "type": "string",
                "description": "The description of the task to update. Must match an existing task."
            },
            "new_status": {
                "type": "string",
                "description": "The new status for the task (e.g., Pendente, Em Andamento, Concluído, Bloqueado).",
                "enum": ["Pendente", "Em Andamento", "Concluído", "Bloqueado"]
            }
        },
        "required": ["task_description", "new_status"]
    }

    async def execute(self, task_description: str, new_status: str, **kwargs: Any) -> ToolResult:
        logger.info(f"UpdateChecklistTaskTool invoked with task_description: '{task_description}', new_status: '{new_status}'")

        # Validate new_status against allowed values (although schema should handle this, good for defense)
        allowed_statuses = self.args_schema["properties"]["new_status"]["enum"]
        if new_status not in allowed_statuses:
            logger.warning(f"UpdateChecklistTaskTool: Invalid new_status provided: '{new_status}'")
            raise ToolError(f"Status inválido '{new_status}'. Status permitidos são: {', '.join(allowed_statuses)}")

        try:
            manager = ChecklistManager()
            await manager._load_checklist() # Load tasks explicitly

            # Check if task exists before attempting update for a clearer message
            # get_task_by_description is synchronous as it operates on already loaded tasks
            task_to_update = manager.get_task_by_description(task_description)
            if not task_to_update:
                return ToolResult(output=f"Falha ao atualizar status da tarefa '{task_description}'. Tarefa não encontrada.")

            if task_to_update['status'] == new_status:
                 return ToolResult(output=f"Tarefa '{task_description}' já está com o status '{new_status}'. Nenhuma alteração realizada.")

            success = await manager.update_task_status(task_description=task_description, new_status=new_status)

            if success:
                return ToolResult(output=f"Status da tarefa '{task_description}' atualizado para '{new_status}'.")
            else:
                # This else might be redundant if the above checks (not found, already same status) are comprehensive
                return ToolResult(output=f"Falha ao atualizar status da tarefa '{task_description}'. Verifique se a tarefa existe e o novo status é diferente do atual.")
        except ToolError as te:
            logger.error(f"UpdateChecklistTaskTool: ToolError updating task: {te}")
            raise te # Re-raise ToolError
        except Exception as e:
            logger.error(f"UpdateChecklistTaskTool: Unexpected error updating task: {e}")
            raise ToolError(f"Erro inesperado ao atualizar status da tarefa no checklist: {e}")
