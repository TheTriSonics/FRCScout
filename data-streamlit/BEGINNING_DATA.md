# Beginning Data

Data is a bit of a nebulous word. It can mean a lot of things but for this
tutorial we'll talk about it in the forms that we'll be working with here.

At the core data is just a series of numbers. We have to give it some structure
to start working with the data. If you're coming at this from a programming
background you might think of this as the 'type' of the data, and that will
apply here, but it is often important to undersetand the structure behind that
to do proper data work.

We'll start with a single number. That's data. Generally not very interesting,
one lone single number, but we'll start with that. You might call this a scalar
value, or possibly a fact depending on context.

Single numbers aren't much though, so next we can organize them into a list,
vector, or array, again depending on context. In Python they are quite literally
refered to as a ```list``` but the term vector will come up often too. There is
a reason for it, but we won't get into that now.

What we'll be working with are two dimensional arrays of data, lists of lists, a
list of vectors, a table, or a dataframe depending on context. It's all the same
idea with subtle nuances here and there. You can also think of it as a
spreadsheet to some extent, but use of that word in this context would be
confusing.

All that to say we'll have stuff that looks like this:


| scouter | scouting_team | match | auto_high | teleop_high | endgame_climb |
| --- | --- | --- | --- | --- | --- |
| Justin | 4004 | 1 | 1 | 4 | 0 |
| David | 264 | 1 | 2 | 8 | 1 |
| Chad | 74 | 1 | 0 | 0 | 0 |


Here each line represents somebody sitting down and scouting a robot for a
match.  So, in the first one Justin watched team 4004 for match 1, and the
values for the remaining ```auto_high```, ```teleop_high```, and
```endgame_high``` are whatever those values are supposed to mean according to
the scouting app. They are "facts" in data terminology. They are the things
that have values that we might want to aggegate in some manner. That could be
summing them all up, taking the mean, median, or mode, min, max, or more.

The other columns, ```scouter```, ```scouting_team```, and ```match``` are what
we could call "dimensions" in data terminology but that is a horribly confusing
term given the area of analysis we'll be working with. When you think in terms
of a pivot table, or similar structure, they are called dimensions. They are the
who, what, where, when, and maybe why of your facts. You need not fill all of
them in; it's not even a technical classification but just a general
approximation. The 'who' here is Justin and 'what' could be 'robot 4004' and
when is 'match 1' at whatever event this record is tied to.

When viewing things from the pivot table perspective you can display facts,
possibly aggregated by some summary, sliced by the dimensions you'd like to use.

Let's say we want to summarize everything that happened in the qualification
matches of an event. The table of data, just for scouting data, would look like
the above but have a column for far more scoring fields. Generally there will
be 10-15 of them. And there will be an entry for every robot (6) for every
qualitifying match (generally 80) giving $6 \cdot 80 = 480$ rows of data with
each containing at least 15 points of information for $480 \cdot 15 = 38,400$
points of raw data. With only 86,400 seconds in an entire day you can see how
digesting these one by one might be problematic.

Even a summary aggregate, taking the average or mean for each team over the
event yields, for 40 teams and 15 datapoints $40 \cdot 15 = 600$ indivual
datapoints. From here you can probably start making sense of it in raw form,
possibly with annotations of your judgements so you don't keep looking back at
the raw data and rethinking or recomputing whatever judgement you made or metric
you calculated.

More formally we could add more columns to the system to summarize the raw data
into ways we'd like to analyze them. For instance you might summarize each
robot's contributions in auto, teleop, and endgame modes giving you 3 columns
of data to concentrate on.

We do this because in our example of 15 facts per robot per match we have
created a 15 dimensional space that each robot occupies in our dataspace. This
is where we see the other meaning of dimension. The other dimensions, the pivot
table definition of them, are being used to "slice" this space into different
subspaces that are easier to work with, or with aggregations that are easier to
understand.

Outside of robots we can think of grocery store sales. The sale of a container
of milk is a fact that has dimensions like a manufacturer, size, type of milk,
type of container, flavoring, and likely more, but also under the product
category of 'milk'. Looking at a printout of milk sales in that detail is not
beneficial for a human unless there is good reason to go digging. For the most
part sales can just be summarized under 'milk' and that's good enough, at least
in our example. We'll also assume the same with the 'cookie' category.

Now if you imagine each cookie sale fact is also tied to a customer you can
plot their purchase habits on an X/Y plane, or you could imagine having them
stand in a room where the floor represented their cookie purchase count in one
direction and their milk purchase count in another.

From there you might be able to see different groups of customers. Some will
buy a mix of both milk and cookies, perhaps some lean heavy toward one more
than the other. And maybe some are outliers that purchase a lot more cookies
than any other group. Still, you an likely see how aranging people in a room
would give you a nice visualization of their purchase habits along these two
categories or dimensions.

If you were to add in a third dimension, say 'bread' we could imagine the people moving higher above the floor to represent their location in that dimension.
Now you might start seeing different grouping patterns among people. You have
a new dimension to analyze.

Now if we add a fourth dimension, say 'soda' (aka pop) we can visualize it by...
wait no we can't. Visualizing data kind of breaks down around the 4th dimension.
So, when you can break things into three important dimensions you an visualize
it in cube space, or projected onto a 2D plane and use something like color
to represent height or depth in the 3rd dimension.

Thankfully math still works in those higher dimensions. We can even figure out
the distance of two robots in 15 dimension space with a formula that's likely
already familiar to you.

If you were tasked to find the distance between two points in 2D space you may
notice there's a way of making a triangle out of the problem.

triangle.png

Finding the difference in the x coordinates gives us one length of the triangle
and finding the difference in the y coorditaes gives us the other. We can find
the distance between the two points, the hypotenuse using Pythagorea's Theorm:
$a^2+b^2=c^2$ or more directly applicable to our case: $c=\sqrt{a^2+b^2}$ where
$a$ and $b$ are the lengths of the triangle's non-hypotenuse sides.

This also works in 3D space where we have three "legs" to our system to find
our final point: $d=\sqrt{\Delta x^2 + \Delta y^2 + \Delta z^2}$ and the
pattern continues on with all the other dimensions.