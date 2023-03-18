import openai
from git import Tree

import guardrails as gd

from pr_drafter.models import PullRequest, Commit


class GenerationService:
    def generate_pr(self, repo_tree: Tree, issue_title: str, issue_body: str, issue_number: int) -> PullRequest:
        raise NotImplementedError

    @staticmethod
    def repo_to_codebase(tree: Tree):
        # Concatenate all the files in the repo,

        codebase = ""
        for blob in tree.traverse():
            # Skip directories
            if blob.type == 'tree':
                continue

            # Skip lock file
            if any(
                blob.path.endswith(ending)
                for ending in ['.lock']
            ):
                continue

            # Separate files with a newline
            if codebase:
                codebase += "\n"

            # Add path
            codebase += f"Path: {blob.path}\n"

            # Add file contents, with line numbers
            blob_text = blob.data_stream.read().decode()
            for i, line in enumerate(blob_text.split('\n')):
                codebase += f"{i+1} {line}\n"

        return codebase


class RailsGenerationService(GenerationService):
    rail_spec = f"""
<rail version="0.1">
<output>
{PullRequest.rail_spec}
</output>
<prompt>
Oh skilled senior software developer, with all your programming might and wisdom, please write a pull request for me.
This is the codebase:
```{{{{codebase}}}}```

Please address the following issue:
```{{{{issue}}}}```

@xml_prefix_prompt

{{output_schema}}

@json_suffix_prompt_v2_wo_none
</prompt>
</rail>
    """

    def generate_pr(self, repo_tree: Tree, issue_title: str, issue_body: str, issue_number: int) -> PullRequest:
        pr_guard = gd.Guard.from_rail_string(
            self.rail_spec,  # make sure to import custom validators before this
            num_reasks=3,
        )
        codebase = self.repo_to_codebase(repo_tree)
        raw_o, dict_o = pr_guard(
            openai.ChatCompletion.create,
            model='gpt-4',
            # openai.Completion.create,
            # model='text-davinci-003',
            max_tokens=1000,
            prompt_params={
                'codebase': codebase,
                'issue': f"Issue #{str(issue_number)}\nTitle: {issue_title}\n\n{issue_body}",
            },
        )
        if dict_o is None:
            raise RuntimeError("No valid PR generated", raw_o)
        return PullRequest.parse_obj(dict_o['pull_request'])


# from langchain import LLMChain
# from langchain.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate, ChatPromptTemplate
# from langchain.chat_models import ChatOpenAI
#
# class SingleLangchainGenerationService(GenerationService):
#     system_message_template = SystemMessagePromptTemplate.from_template(
#         "You are a helpful contributor to the project, tasked with preparing pull requests for issues."
#     )
#     human_template = HumanMessagePromptTemplate.from_template("""
# Given the following codebase:
# {codebase}
#
# And the following issue:
# Title: {issue_title}
# Body: {issue_body}
#
# ONLY return a valid git patch (no other text is necessary). Omit the `index 0000000..0000000` line.
#     """)
#
#     def generate_patch(self, repo_tree: Tree, issue_title: str, issue_body: str) -> str:
#         codebase = self.repo_to_codebase(repo_tree)
#         chat = ChatOpenAI(temperature=0)
#         chat_prompt = ChatPromptTemplate.from_messages([
#             self.system_message_template,
#             self.human_template,
#         ])
#
#         chain = LLMChain(llm=chat, prompt=chat_prompt, verbose=True)
#         return chain.run(
#             codebase=codebase,
#             issue_title=issue_title,
#             issue_body=issue_body,
#         )
#
#     def generate_pr(self, repo_tree: Tree, issue_title: str, issue_body: str) -> PullRequest:
#         patch = self.generate_patch(repo_tree, issue_title, issue_body)
#         # TODO describe the patch in the PR body
#         return PullRequest(
#             title=f"Fix {issue_title}",
#             body="",
#             commits=[
#                 Commit(
#                     message=f"Fix {issue_title}",
#                     diff=patch,
#                 )
#             ],
#         )
