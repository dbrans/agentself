## Reference Passing to LLMs

Most repl systems are using strings as the data type that gets passed between repl and llm. 

You could imagine however a system where the RLM passes references to objects in the repl (e.g. '#refA{type="list[str]"})'. I feel an urge to keep things as python objects in the repl and only convert them into a string representation of exactly what the llm needs to know (json or reference+type or pickled object) only when it is time to invoke the llm. And perhaps the llm could write code or a function to extract the actual information it needs from the repl. 

Would that provide any benefits? 

https://deepwiki.com/search/this-repo-seems-to-use-regular_40848a34-e32b-46d2-90b9-ebcb5359d2e8?mode=deep

## RLM Sequence Diagram

https://deepwiki.com/search/draw-a-sequence-diagram-betwee_e5b297e2-d12f-4e00-9f5d-6172b571839e?mode=deep

## How REPL state evolves

https://deepwiki.com/search/help-me-understand-how-repl-st_19866ba7-59dc-43e8-9933-84c8326bd37b?mode=deep

## async, parallel, nested repl calls

https://deepwiki.com/search/how-does-asynchronous-code-lik_9a716df9-5f5c-453d-8bd6-388fd62a4994?mode=deep