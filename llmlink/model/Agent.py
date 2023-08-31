from langchain.tools import Tool
from .BaseModel import BaseModel

PREFIX = 'Answer the following question as best you can. You have access to the following tools:'
SUFFIX = 'Begin\n\nQuestion: {question}\n'
INSTRUCTIONS = 'Use the following format:\n\nQuestion: the input question you must answer\nThought: you should always think about what to do next\nAction: the action to take, should be one of {tool_names}\nAction Input: The input to the action\nObservation: the result of the action\n... (this Thought/Action/Action Input/Observation can repeat N times)\nThought: I now know the final answer\nFinal Answer: the final answer to the original input question'


class Agent(BaseModel):
    """
    Custom agent which implements the ReAct framework using an LLM

    Parameters
    ----------
    llm : Any
        Any LLM-like object that runs in a functional manner. i.e. llm('How are you today?') returns
        a suitable response
    tools : langchain Tool or list of Tools
        Tools for the Agent to have access to
    verbose : bool (default False)
        Whether to print intermediate outputs
    """

    def __init__(
            self,
            llm,
            tools,
            verbose=False
    ):
        super().__init__()
        self.llm = llm
        self.tools = tools
        self.verbose = verbose

    @property
    def llm(self):
        return self._llm

    @llm.setter
    def llm(self, value):
        self._llm = value

    @property
    def tools(self):
        return self._tools

    @tools.setter
    def tools(self, value):

        if isinstance(value, list):
            if not all([isinstance(v, Tool) for v in value]):
                raise TypeError('All tools must be langchain Tool objects')

        elif isinstance(value, Tool):
            value = [value]

        else:
            raise TypeError(
                f'tools must be langchain Tool or list of Tools, got {type(value)}')

        self._tools = value

    @property
    def verbose(self):
        return self._verbose

    @verbose.setter
    def verbose(self, value):

        if not isinstance(value, bool):
            raise TypeError(f'verbose must be bool, got {type(value)}')

        self._verbose = value

    @property
    def tool_descriptions(self):
        return '\n\n'.join([f'{tool.name}: {tool.description}' for tool in self.tools])

    @property
    def tool_dict(self):
        return {
            tool.name: tool for tool in self.tools
        }

    @property
    def tool_names(self):
        return [tool.name for tool in self.tools]

    def create_prompt(
            self,
            question,
            prefix=PREFIX,
            suffix=SUFFIX,
            instructions=INSTRUCTIONS
    ):
        """
        Format the initial prompt for the LLM
        """
        return f'{prefix}\n\n{self.tool_descriptions}\n\n{instructions}\n\n{suffix}'.format(
            question=question,
            tool_names=self.tool_names
        )

    def run_tool(
            self,
            tool_name,
            tool_input
    ):
        """
        Run the specified tool
        """

        the_tool = self.tool_dict.get(tool_name)

        if the_tool:
            try:
                return the_tool(tool_input)
            except Exception as e:
                return(f'Tool encountered an error: {e}')
        else:
            return f'No tool with the name {tool_name} found'

    def parse_output(
            self,
            output
    ):
        """
        Parse the output from the model
        """

        lines = output.splitlines()

        for idx in range(len(lines)):

            if ':' in lines[idx]:
                type_of_response = lines[idx].split(':')[0].strip()

                if type_of_response == 'Action':
                    tool = ':'.join(lines[idx].split(':')[1:]).strip()

                    if lines[idx + 1].split(':')[0].strip() != 'Action Input':
                        print('Possible problem parsing action input')
                    tool_input = lines[idx + 1].split(':')[1].strip()

                    # Testing this one out
                    for action_idx in range(idx + 2, len(lines)):
                        if lines[action_idx].startswith('Observation:'):
                            break
                        else:
                            tool_input += '\n' + lines[action_idx]

                    
                    return {'Action': 'tool', 'Tool': tool, 'Input': tool_input, 'Thought': '\n'.join(lines[:idx])}

                elif type_of_response == 'Final Answer':
                    final_answer = lines[idx].split(':')[1].strip()
                    return {'Action': 'answer', 'Answer': final_answer, 'Thought': '\n'.join(lines[:idx])}
        return output + '\n' + 'Warning: No parsable action detected. Be sure to '

    def run(
            self,
            question
    ):
        """
        Run the Agent for a question

        Parameters
        ----------
        question : str
            The input question for the Agent

        Returns
        -------
        response : dict
            Dictionary with the keys 'response' and 'full_text', containing
            the final response from the model and the full text generated by the model
            and the tools, respectively
        """
        prompt = self.create_prompt(question)

        if self.verbose:
            print('INITIAL PROMPT:')
            print('\n')
            print(prompt)
            print('\n\n')

        while True:
            response = self.llm(prompt)
            
            if self.verbose:
                print('MODEL RESPONSE:')
                print('\n')
                print(response)
                print('\n\n')

            action = self.parse_output(response)

            if self.verbose:
                print('PARSED ACTION:')
                print('\n')
                print(action)
                print('\n\n')

            if action['Action'] == 'tool':
                tool_response = self.run_tool(
                    action['Tool'],
                    action['Input']
                )

                if tool_response == '':
                    tool_response = 'Tool returned no results'
                prompt += f'{action["Thought"]}\nAction: {action["Tool"]}\nAction Input: {action["Input"]}\nObservation: {tool_response}\n'

                if self.verbose:
                    print('NEW PROMPT:')
                    print('\n')
                    print(prompt)
                    print('\n\n')

            elif action['Action'] == 'answer':
                prompt += f'{action["Thought"]}\nFinal Answer: {action["Answer"]}'

                if self.verbose:
                    print('FINAL TEXT:')
                    print('\n')
                    print(prompt)
                return {
                    'response': action['Answer'],
                    'full_text': prompt
                }
