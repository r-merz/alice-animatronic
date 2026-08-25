# Todo List Capability

class TodoList:
    def __init__(self):
        self.tasks = []

    def add_task(self, task):
        self.tasks.append(task)

    def view_tasks(self):
        return self.tasks

    def edit_task(self, index, new_task):
        self.tasks[index] = new_task

    def remind_deadlines(self):
        # Implement reminder logic here
        pass
