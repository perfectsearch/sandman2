Sandman 2
=========

Goals:

We want to make it easy to develop a project, and the projects dependencies source code outside of a monolithic project.

A depends on B
B depends on C
A depends on C

A -> B -> C
  -> C

If we need to include the binaries or the source, or both, we want them to be available to A's development.

1) We don't want to tightly integrate build tools.
2) We want to be extensible. (Can we add an alternative build tool?)
3) We want to be easily scriptable
4) We have to support branches
5) We need to provide server hooks or administrative tools to assist in repo management.
6) We want to provide hooks to other services information about our repos. 


We need to support the following functions -

- BZR
- Git
- Git - Annex
- SVN

sandbox - All of the components that belong to a single component
component - A single component that contains aspects ( like code, test, and built )
aspect - Not all data belongs in a code aspect, such as test or built. You could invent other types of aspects, such as data, or profiling
sandbox type - dev, test, memcheck, official, continuous, or roll your own. This adjusts what aspects are retrieved, and what environment variables are set.

We need to support

User tasks:

sm init - Get all of the initial aspects
sm up - Update the current aspects
sm build - Runs script in sandbox
sm test - Runs script in sandbox
sm custom - Custom commands can be added by end user.
sm commit(ci) - Commit all user aspects
sm push - Pushes changes
sm revno - Get the current revision ids
sm remove - Removes all traces of the sandbox
sm status - Get the current status of aspects
sm tools - Get the tools that need to be installed for this sandbox and what the system status is of those tools

Admin tasks:

sm buildorder ( Get build order and options that include what needs to built, build above, build up to )
sm repos ( List all repos )
sm changed ( Can poll for changes, the changes should update an intermediate DB of recent changes with commit hooks? )
sm repo add
sm repo remove

Configurations:

Aspects
Branches
Components
Source Control
Sandbox Types - This changes what is checked out and what environment variables are set.



