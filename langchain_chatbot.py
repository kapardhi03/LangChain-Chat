# -*- coding: utf-8 -*-
"""LangChain_ChatBot.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1kUS-a1YPxtuuili9ll2EiPiik7ieg0Uu
"""

from google.colab import userdata
openAI_API = userdata.get('API_KEY')

"""# basic chat implementation"""

# Commented out IPython magic to ensure Python compatibility.
# %pip install --upgrade --quiet langchain langchain-openai langchain-chroma

import dotenv

dotenv.load_dotenv()

from langchain_openai import ChatOpenAI

chat = ChatOpenAI(model="gpt-3.5-turbo-1106", temperature=0.2,openai_api_key=openAI_API)

"""If we invoke our chat model, the output is an AIMessage:"""

from langchain_core.messages import HumanMessage

chat.invoke(
    [
        HumanMessage(
            content="Translate this sentence from English to Telugu: I love programming."
        )
    ]
)

"""The model on its own does not have any concept of state. For example, if you ask a followup question:"""

chat.invoke([HumanMessage(content="What did you just say?")])

"""We can see that it doesn't take the previous conversation turn into context, and cannot answer the question.

To get around this, we need to pass the entire conversation history into the model. Let's see what happens when we do that:
"""

from langchain_core.messages import AIMessage

chat.invoke(
    [
        HumanMessage(
            content="Translate this sentence from English to Telugu: I love programming."
        ),
        AIMessage(content="నాకు ప్రోగ్రమింగ్ నచ్చు."),
        HumanMessage(content="What did you just say?"),
    ]
)

"""**Prompt templates**

Let's define a prompt template to make formatting a bit easier. We can create a chain by piping it into the model:
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful assistant. Answer all questions to the best of your ability.",
        ),
        MessagesPlaceholder(variable_name="messages"),
    ]
)

chain = prompt | chat

"""The MessagesPlaceholder above inserts chat messages passed into the chain's input as chat_history directly into the prompt. Then, we can invoke the chain like this:


"""



"""**Message history**

As a shortcut for managing the chat history, we can use a MessageHistory class, which is responsible for saving and loading chat messages.

There are many built-in message history integrations that persist messages to a variety of databases, but for this quickstart we'll use a in-memory, demo message history called ChatMessageHistory.


"""

from langchain.memory import ChatMessageHistory

demo_ephemeral_chat_history = ChatMessageHistory()

demo_ephemeral_chat_history.add_user_message("hi!")

demo_ephemeral_chat_history.add_ai_message("whats up?")
demo_ephemeral_chat_history.add_user_message("nothing")
demo_ephemeral_chat_history.add_ai_message("Ok Good bye")

demo_ephemeral_chat_history.messages

demo_ephemeral_chat_history.add_user_message(
    "Translate this sentence from English to French: I love programming."
)

response = chain.invoke({"messages": demo_ephemeral_chat_history.messages})

response

demo_ephemeral_chat_history.add_ai_message(response)

demo_ephemeral_chat_history.add_user_message("What did you just say?")

chain.invoke({"messages": demo_ephemeral_chat_history.messages})



"""**Retrievers**

We can set up and use a Retriever to pull domain-specific knowledge for our chatbot. To show this, let's expand the simple chatbot we created above to be able to answer questions about Document
"""

# Commented out IPython magic to ensure Python compatibility.
# %pip install --upgrade --quiet langchain-chroma beautifulsoup4

from langchain_community.document_loaders import WebBaseLoader

loader = WebBaseLoader("https://docs.smith.langchain.com/overview")
data = loader.load()

""" we split it into smaller chunks that the LLM's context window can handle and store it in a vector database:"""

from langchain_text_splitters import RecursiveCharacterTextSplitter

text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=10)
all_splits = text_splitter.split_documents(data)

"""Then we embed and store those chunks in a vector database:"""

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings


vectorstore = Chroma.from_documents(
    documents=all_splits,
    embedding=OpenAIEmbeddings(openai_api_key=openAI_API)
)

"""#Retrieval

And finally, let's create a retriever from our initialized vectorstore:
"""

# k is the number of chunks to retrieve
retriever = vectorstore.as_retriever(k=4)

docs = retriever.invoke("What is langsmith?")

docs[0].metadata["description"]

retriever = vectorstore.as_retriever(k=10)

docs = retriever.invoke("How langsmith is used for testing?")

docs[0].metadata["description"]



"""**Handling documents**

Let's modify our previous prompt to accept documents as context. We'll use a create_stuff_documents_chain helper function to "stuff" all of the input documents into the prompt, which also conveniently handles formatting. We use the ChatPromptTemplate.from_messages method to format the message input we want to pass to the model, including a MessagesPlaceholder where chat history messages will be directly injected:
"""

from langchain.chains.combine_documents import create_stuff_documents_chain

chat = ChatOpenAI(model="gpt-3.5-turbo-1106",openai_api_key=openAI_API)

question_answering_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Answer the user's questions based on the below context:\n\n{context}",
        ),
        MessagesPlaceholder(variable_name="messages"),
    ]
)

document_chain = create_stuff_documents_chain(chat, question_answering_prompt)

from langchain.memory import ChatMessageHistory

demo_ephemeral_chat_history = ChatMessageHistory()

demo_ephemeral_chat_history.add_user_message("how can langsmith help with testing?")

document_chain.invoke(
    {
        "messages": demo_ephemeral_chat_history.messages,
        "context": docs,
    }
)

from langchain.memory import ChatMessageHistory

demo_ephemeral_chat_history = ChatMessageHistory()

demo_ephemeral_chat_history.add_user_message("what are the usecases of langsmith?")

document_chain.invoke(
    {
        "messages": demo_ephemeral_chat_history.messages,
        "context": docs,
    }
)



"""**Creating a retrieval chain**

Next, let's integrate our retriever into the chain. Our retriever should retrieve information relevant to the last message we pass in from the user, so we extract it and use that as input to fetch relevant docs, which we add to the current chain as context. We pass context plus the previous messages into our document chain to generate a final answer.

We also use the RunnablePassthrough.assign() method to pass intermediate steps through at each invocation. Here's what it looks like:
"""

from typing import Dict

from langchain_core.runnables import RunnablePassthrough


def parse_retriever_input(params: Dict):
    return params["messages"][-1].content


retrieval_chain = RunnablePassthrough.assign(
    context=parse_retriever_input | retriever,
).assign(
    answer=document_chain,
)

response = retrieval_chain.invoke(
    {
        "messages": demo_ephemeral_chat_history.messages,
    }
)

response

demo_ephemeral_chat_history.add_ai_message(response["answer"])

demo_ephemeral_chat_history.add_user_message("tell me more about that!")

retrieval_chain.invoke(
    {
        "messages": demo_ephemeral_chat_history.messages,
    },
)



"""Nice! Our chatbot can now answer domain-specific questions in a conversational way.

As an aside, if you don't want to return all the intermediate steps, you can define your retrieval chain like this using a pipe directly into the document chain instead of the final .assign() call:


"""

retrieval_chain_with_only_answer = (
    RunnablePassthrough.assign(
        context=parse_retriever_input | retriever,
    )
    | document_chain
)

retrieval_chain_with_only_answer.invoke(
    {
        "messages": demo_ephemeral_chat_history.messages,
    },
)



"""Query transformation

"""

from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableBranch

# We need a prompt that we can pass into an LLM to generate a transformed search query

chat = ChatOpenAI(model="gpt-3.5-turbo-1106", temperature=0.2,openai_api_key=openAI_API)

query_transform_prompt = ChatPromptTemplate.from_messages(
    [
        MessagesPlaceholder(variable_name="messages"),
        (
            "user",
            "Given the above conversation, generate a search query to look up in order to get information relevant to the conversation. Only respond with the query, nothing else.",
        ),
    ]
)

query_transforming_retriever_chain = RunnableBranch(
    (
        lambda x: len(x.get("messages", [])) == 1,
        # If only one message, then we just pass that message's content to retriever
        (lambda x: x["messages"][-1].content) | retriever,
    ),
    # If messages, then we pass inputs to LLM chain to transform the query, then pass to retriever
    query_transform_prompt | chat | StrOutputParser() | retriever,
).with_config(run_name="chat_retriever_chain")

document_chain = create_stuff_documents_chain(chat, question_answering_prompt)

conversational_retrieval_chain = RunnablePassthrough.assign(
    context=query_transforming_retriever_chain,
).assign(
    answer=document_chain,
)

demo_ephemeral_chat_history = ChatMessageHistory()

demo_ephemeral_chat_history.add_user_message("how can langsmith help with testing?")

response = conversational_retrieval_chain.invoke(
    {"messages": demo_ephemeral_chat_history.messages},
)

demo_ephemeral_chat_history.add_ai_message(response["answer"])

response

demo_ephemeral_chat_history.add_user_message("tell me more about that!")

conversational_retrieval_chain.invoke(
    {"messages": demo_ephemeral_chat_history.messages}
)

"""# Memory management

##Memory to Store

###Neo4j
"""

# Commented out IPython magic to ensure Python compatibility.
# %pip install neo4j

from langchain_community.chat_message_histories import Neo4jChatMessageHistory

history = Neo4jChatMessageHistory(
    url="bolt://localhost:7687",
    username="neo4j",
    password="password",
    session_id="session_id_1",
)

history.add_user_message("hi!")

history.add_ai_message("whats up?")

history.messages

"""### Stremlit"""

# Commented out IPython magic to ensure Python compatibility.
# %pip install streamlit

from langchain_community.chat_message_histories import (
    StreamlitChatMessageHistory,
)

history = StreamlitChatMessageHistory(key="chat_messages")

history.add_user_message("hi!")
history.add_ai_message("whats up?")







"""##We can use it directly to store conversation turns for our chain:


"""

demo_ephemeral_chat_history = ChatMessageHistory()

input1 = "Translate this sentence from English to French: I love programming."

demo_ephemeral_chat_history.add_user_message(input1)

response = chain.invoke(
    {
        "messages": demo_ephemeral_chat_history.messages,
    }
)

demo_ephemeral_chat_history.add_ai_message(response)

input2 = "What did I just ask you?"

demo_ephemeral_chat_history.add_user_message(input2)

chain.invoke(
    {
        "messages": demo_ephemeral_chat_history.messages,
    }
)

"""##**Automatic history management**

The previous examples pass messages to the chain explicitly. This is a completely acceptable approach, but it does require external management of new messages. LangChain also includes an wrapper for LCEL chains that can handle this process automatically called ***RunnableWithMessageHistory.***

To show how it works, let's slightly modify the above prompt to take a final input variable that populates a HumanMessage template after the chat history. This means that we will expect a chat_history parameter that contains all messages BEFORE the current messages instead of all messages:


"""

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful assistant. Answer all questions to the best of your ability.",
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
    ]
)

chain = prompt | chat

"""We'll pass the latest input to the conversation here and let the RunnableWithMessageHistory class wrap our chain and do the work of appending that input variable to the chat history."""

from langchain_core.runnables.history import RunnableWithMessageHistory

demo_ephemeral_chat_history_for_chain = ChatMessageHistory()

chain_with_message_history = RunnableWithMessageHistory(
    chain,
    lambda session_id: demo_ephemeral_chat_history_for_chain,
    input_messages_key="input",
    history_messages_key="chat_history",
)

"""This class takes a few parameters in addition to the chain that we want to wrap:

A factory function that returns a message history for a given session id. This allows your chain to handle multiple users at once by loading different messages for different conversations.
An input_messages_key that specifies which part of the input should be tracked and stored in the chat history. In this example, we want to track the string passed in as input.

A history_messages_key that specifies what the previous messages should be injected into the prompt as. Our prompt has a MessagesPlaceholder named chat_history, so we specify this property to match.

(For chains with multiple outputs) an output_messages_key which specifies which output to store as history. This is the inverse of input_messages_key.

We can invoke this new chain as normal, with an additional configurable field that specifies the particular session_id to pass to the factory function. This is unused for the demo, but in real-world chains, you'll want to return a chat history corresponding to the passed session:
"""



"""**Modifying chat history**

Modifying stored chat messages can help your chatbot handle a variety of situations. Here are some examples:


"""



"""##**Trimming messages**

LLMs and chat models have limited context windows, and even if you're not directly hitting limits, you may want to limit the amount of distraction the model has to deal with. One solution is to only load and store the most recent n messages. Let's use an example history with some preloaded messages:
"""

demo_ephemeral_chat_history = ChatMessageHistory()

demo_ephemeral_chat_history.add_user_message("Hey there! I'm Nemo.")
demo_ephemeral_chat_history.add_ai_message("Hello!")
demo_ephemeral_chat_history.add_user_message("How are you today?")
demo_ephemeral_chat_history.add_ai_message("Fine thanks!")

demo_ephemeral_chat_history.messages

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful assistant. Answer all questions to the best of your ability.",
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
    ]
)

chain = prompt | chat

chain_with_message_history = RunnableWithMessageHistory(
    chain,
    lambda session_id: demo_ephemeral_chat_history,
    input_messages_key="input",
    history_messages_key="chat_history",
)

chain_with_message_history.invoke(
    {"input": "What's my name?"},
    {"configurable": {"session_id": "unused"}},
)

"""We can see the chain remembers the preloaded name.

But let's say we have a very small context window, and we want to trim the number of messages passed to the chain to only the 2 most recent ones. We can use the clear method to remove messages and re-add them to the history. We don't have to, but let's put this method at the front of our chain to ensure it's always called:


"""

def trim_messages(chain_input):
    stored_messages = demo_ephemeral_chat_history.messages
    if len(stored_messages) <= 2:
        return False

    demo_ephemeral_chat_history.clear()

    for message in stored_messages[-2:]:
        demo_ephemeral_chat_history.add_message(message)

    return True


chain_with_trimming = (
    RunnablePassthrough.assign(messages_trimmed=trim_messages)
    | chain_with_message_history
)

"""Let's call this new chain and check the messages afterwards:"""

chain_with_trimming.invoke(
    {"input": "Where does P. Sherman live?"},
    {"configurable": {"session_id": "unused"}},
)

demo_ephemeral_chat_history.messages



"""And we can see that our history has removed the two oldest messages while still adding the most recent conversation at the end. The next time the chain is called, trim_messages will be called again, and only the two most recent messages will be passed to the model. In this case, this means that the model will forget the name we gave it the next time we invoke it:


"""

chain_with_trimming.invoke(
    {"input": "What is my name?"},
    {"configurable": {"session_id": "unused"}},
)

demo_ephemeral_chat_history.messages



"""##**Summary memory**

We can use this same pattern in other ways too. For example, we could use an additional LLM call to generate a summary of the conversation before calling our chain. Let's recreate our chat history and chatbot chain:
"""

def summarize_messages(chain_input):
    stored_messages = demo_ephemeral_chat_history.messages
    if len(stored_messages) == 0:
        return False
    summarization_prompt = ChatPromptTemplate.from_messages(
        [
            MessagesPlaceholder(variable_name="chat_history"),
            (
                "user",
                "Distill the above chat messages into a single summary message. Include as many specific details as you can.",
            ),
        ]
    )
    summarization_chain = summarization_prompt | chat

    summary_message = summarization_chain.invoke({"chat_history": stored_messages})

    demo_ephemeral_chat_history.clear()

    demo_ephemeral_chat_history.add_message(summary_message)

    return True


chain_with_summarization = (
    RunnablePassthrough.assign(messages_summarized=summarize_messages)
    | chain_with_message_history
)

chain_with_summarization.invoke(
    {"input": "What did I say my name was?"},
    {"configurable": {"session_id": "unused"}},
)

demo_ephemeral_chat_history.messages



"""#Tool Calling

We use the term "tool calling" interchangeably with "function calling". Although function calling is sometimes meant to refer to invocations of a single function, we treat all models as though they can return multiple tool or function calls in each message.

Tool calling allows a model to respond to a given prompt by generating output that matches a user-defined schema. While the name implies that the model is performing some action, this is actually not the case! The model is coming up with the arguments to a tool, and actually running the tool (or not) is up to the user - for example, if you want to extract output matching some schema from unstructured text, you could give the model an "extraction" tool that takes parameters matching the desired schema, then treat the generated output as your final result.

A tool call includes a name, arguments dict, and an optional identifier. The arguments dict is structured

***{argument_name: argument_value}.***

Many LLM providers, including Anthropic, Cohere, Google, Mistral, OpenAI, and others, support variants of a tool calling feature.

These features typically allow requests to the LLM to include available tools and their schemas, and for responses to include calls to these tools.

*For instance, given a search engine tool, an LLM might handle a query by first issuing a call to the search engine.*

The system calling the LLM can receive the tool call, execute it, and return the output to the LLM to inform its response. LangChain includes a suite of built-in tools and supports several methods for defining your own custom tools. Tool-calling is extremely useful for building tool-using chains and agents, and for getting structured outputs from models more generally.

Providers adopt different conventions for formatting tool schemas and tool calls.

##Anthropic

For instance, Anthropic returns tool calls as parsed structures within a larger content block:
"""

[
  {
    "text": "<thinking>\nI should use a tool.\n</thinking>",
    "type": "text"
  },
  {
    "id": "id_value",
    "input": {"arg_name": "arg_value"},
    "name": "tool_name",
    "type": "tool_use"
  }
]

"""##OpenAI

whereas OpenAI separates tool calls into a distinct parameter, with arguments as JSON strings:
"""

{
  "tool_calls": [
    {
      "id": "id_value",
      "function": {
        "arguments": '{"arg_name": "arg_value"}',
        "name": "tool_name"
      },
      "type": "function"
    }
  ]
}

"""##Request: Passing tools to model

For a model to be able to invoke tools, you need to pass tool schemas to it when making a chat request. LangChain ChatModels supporting tool calling features implement a .bind_tools method, which receives a list of LangChain tool objects, Pydantic classes, or JSON Schemas and binds them to the chat model in the provider-specific expected format. Subsequent invocations of the bound chat model will include tool schemas in every call to the model API.

###**Defining tool schemas: LangChain Tool**

For example, we can define the schema for custom tools using the **@tool** decorator on Python functions:
"""

from langchain_core.tools import tool


@tool
def add(a: int, b: int) -> int:
    """Adds a and b.

    Args:
        a: first int
        b: second int
    """
    return a + b


@tool
def multiply(a: int, b: int) -> int:
    """Multiplies a and b.

    Args:
        a: first int
        b: second int
    """
    return a * b


tools = [add, multiply]

"""###Defining tool schemas: Pydantic class
We can equivalently define the schema using Pydantic. Pydantic is useful when your tool inputs are more complex:
"""

from langchain_core.pydantic_v1 import BaseModel, Field


# Note that the docstrings here are crucial, as they will be passed along
# to the model along with the class name.
class add(BaseModel):
    """Add two integers together."""

    a: int = Field(..., description="First integer")
    b: int = Field(..., description="Second integer")


class multiply(BaseModel):
    """Multiply two integers together."""

    a: int = Field(..., description="First integer")
    b: int = Field(..., description="Second integer")


tools = [add, multiply]





"""##**Request: Forcing a tool call**

When you just use bind_tools(tools), the model can choose whether to return one tool call, multiple tool calls, or no tool calls at all. Some models support a tool_choice parameter that gives you some ability to force the model to call a tool. For models that support this, you can pass in the name of the tool you want the model to always call tool_choice="xyz_tool_name". Or you can pass in tool_choice="any" to force the model to call at least one tool, without specifying which tool specifically.
"""

# always_multiply_llm = llm.bind_tools([multiply], tool_choice="multiply")

# always_multiply_llm = llm.bind_tools([multiply], tool_choice="any")



"""##Response: Reading tool calls from model output

If tool calls are included in a LLM response, they are attached to the corresponding AIMessage or AIMessageChunk (when streaming) as a list of ToolCall objects in the .tool_calls attribute. A ToolCall is a typed dict that includes a tool name, dict of argument values, and (optionally) an identifier. Messages with no tool calls default to an empty list for this attribute.
"""

# query = "What is 3 * 12? Also, what is 11 + 49?"

# llm_with_tools.invoke(query).tool_calls

"""The .tool_calls attribute should contain valid tool calls. Note that on occasion, model providers may output malformed tool calls (e.g., arguments that are not valid JSON). When parsing fails in these cases, instances of InvalidToolCall are populated in the .invalid_tool_calls attribute. An InvalidToolCall can have a name, string arguments, identifier, and error message.

If desired, output parsers can further process the output. For example, we can convert back to the original Pydantic class:


"""

# from langchain_core.output_parsers.openai_tools import PydanticToolsParser

# chain = llm_with_tools | PydanticToolsParser(tools=[multiply, add])
# chain.invoke(query)



"""##Request: Passing tool outputs to model

If we're using the model-generated tool invocations to actually call tools and want to pass the tool results back to the model, we can do so using ToolMessages.
"""

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-3.5-turbo-0125",openai_api_key=openAI_API)

llm_with_tools = llm.bind_tools(tools)

always_multiply_llm = llm.bind_tools([multiply], tool_choice="multiply")

always_call_tool_llm = llm.bind_tools([add, multiply], tool_choice="any")

query = "What is 3 * 12? Also, what is 11 + 49?"

llm_with_tools.invoke(query).tool_calls

from langchain_core.output_parsers.openai_tools import PydanticToolsParser

chain = llm_with_tools | PydanticToolsParser(tools=[multiply, add])
chain.invoke(query)

async for chunk in llm_with_tools.astream(query):
    print(chunk.tool_call_chunks)

first = True
async for chunk in llm_with_tools.astream(query):
    if first:
        gathered = chunk
        first = False
    else:
        gathered = gathered + chunk

    print(gathered.tool_call_chunks)

first = True
async for chunk in llm_with_tools.astream(query):
    if first:
        gathered = chunk
        first = False
    else:
        gathered = gathered + chunk

    print(gathered.tool_calls)

@tool
def add(a: int, b: int) -> int:
    """Adds a and b.

    Args:
        a: first int
        b: second int
    """
    return a + b


@tool
def multiply(a: int, b: int) -> int:
    """Multiplies a and b.

    Args:
        a: first int
        b: second int
    """
    return a * b


tools = [add, multiply]
llm_with_tools = llm.bind_tools(tools)

messages = [HumanMessage(query)]
ai_msg = llm_with_tools.invoke(messages)
messages.append(ai_msg)

for tool_call in ai_msg.tool_calls:
    selected_tool = {"add": add, "multiply": multiply}[tool_call["name"].lower()]
    tool_output = selected_tool.invoke(tool_call["args"])
    messages.append(ToolMessage(tool_output, tool_call_id=tool_call["id"]))

messages

llm_with_tools.invoke(messages)

"""###few short prompting"""

llm_with_tools.invoke(
    "Whats 119 times 8 minus 20. Don't do any math yourself, only use tools for math. Respect order of operations"
).tool_calls

"""The model shouldn't be trying to add anything yet, since it technically can't know the results of 119 * 8 yet.

By adding a prompt with some examples we can correct this behavior:


"""

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

examples = [
    HumanMessage(
        "What's the product of 317253 and 128472 plus four", name="example_user"
    ),
    AIMessage(
        "",
        name="example_assistant",
        tool_calls=[
            {"name": "multiply", "args": {"x": 317253, "y": 128472}, "id": "1"}
        ],
    ),
    ToolMessage("16505054784", tool_call_id="1"),
    AIMessage(
        "",
        name="example_assistant",
        tool_calls=[{"name": "add", "args": {"x": 16505054784, "y": 4}, "id": "2"}],
    ),
    ToolMessage("16505054788", tool_call_id="2"),
    AIMessage(
        "The product of 317253 and 128472 plus four is 16505054788",
        name="example_assistant",
    ),
]

system = """You are bad at math but are an expert at using a calculator.

Use past tool usage as an example of how to correctly use the tools."""
few_shot_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system),
        *examples,
        ("human", "{query}"),
    ]
)

chain = {"query": RunnablePassthrough()} | few_shot_prompt | llm_with_tools
chain.invoke("Whats 119 times 8 minus 20").tool_calls

