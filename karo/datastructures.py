from copy import deepcopy

class BoundSafeList(list):
    """
    A list with default behavior when accessing OutOfRange indices.

    Use like ``list()``, except that accessing elements outside of ``[0,
    len(self))`` returns a copy of ``self.outOfBounds_value``.

    Parameters
    ----------
    outOfBounds_value : arbitrary
        the value to return for out of bounds element access.
    """
    def __init__(self, *args, outOfBounds_value=None, **kwargs):
        self.outOfBounds_value = outOfBounds_value
        super().__init__(*args, **kwargs)
    
    def __getitem__(self, key):
        # Note that if key is a slice, we return a list instead of BoundSafeList
        if isinstance(key, int):
            if key < 0 or key >= len(self):
                return deepcopy(self.outOfBounds_value) # copy, in case we have a mutable value (e.g. Track uses [])
            else:
                return super().__getitem__(key)
        elif isinstance(key, slice):
            start, stop, step = key.start, key.stop, key.step
            if start is None:
                start = 0
            if stop is None:
                stop = len(self)
            if step is None:
                step = 1
                
            return [self[i] for i in range(start, stop, step)]

###############################################################################
            
class EmptyList(Exception):
    pass

class OLLNode:
    """
    One node of the `OrderedLinkedList`.

    Parameters
    ----------
    t : float
        the time of this node
    data : <arbitrary>
        the data to associate with / store in the node
    nextNode : OLLNode (optional)
        the next node in the list.

    See also
    --------
    OrderedLinkedList
    """
    def __init__(self, t, data, nextNode=None):
        self.t = t
        self.data = data
        self.next = nextNode
        
    def __str__(self):
        return "({}, {})".format(self.t, str(self.data))

class OrderedLinkedList:
    """
    A singly linked list, ordered by a scalar parameter called time.

    Intended for use as an updateable queue.

    See also
    --------
    OLLNode

    Examples
    --------
    >>> lst = OrderedLinkedList()
    ... lst.insert(5, "test")
    ... lst.insert(6, [1, 2, 3])
    ... lst.insert(3, "this will be first")
    ... t, data = lst.pop() # t = 3, data = "this will be first"
    ... lst.remove(5, 8)    # Now the list is empty again
    ... lst.insert(4.7, "another test")
    ... print(lst)          # Prints contents to screen
    """
    def __init__(self):
        self.head = OLLNode(None, None, None)
        
    def __str__(self):
        curnode = self.head.next
        if curnode is None:
            return "[]"
        else:
            ret = ""
            while curnode:
                ret += "{}\n".format(str(curnode))
                curnode = curnode.next
            return ret[:-1]
        
    def __len__(self):
        """ warning: this is O(n) """
        L = 0
        curnode = self.head.next
        while curnode:
            L += 1
            curnode = curnode.next
        return L
        
    def checkNotEmpty(self):
        """ Raises `!EmptyList` if list is empty """
        if self.head.next is None:
            raise EmptyList()
        
    def lastNodeBefore(self, t, startNode=None):
        """
        Get the last node with time smaller than `!t`.

        Parameters
        ----------
        t : float
            the time to search for
        startNode : OLLNode (optional)
            the node where the search should start, defaults to the head of the
            list. Note that if ``startNode.t >= t``, `!startNode` is returned.

        Returns
        -------
        OLLNode
            the wanted node
        """
        if startNode is None:
            curnode = self.head
        else:
            curnode = startNode
            
        while curnode.next and curnode.next.t < t:
            curnode = curnode.next
        return curnode
        
    def insert(self, t, data):
        """
        Insert the given data into the right place in the list

        Parameters
        ----------
        t : float
            the time to associate the data with
        data : <arbitrary>
            the data to store

        See also
        --------
        remove
        """
        curnode = self.lastNodeBefore(t)
        curnode.next = OLLNode(t, data, curnode.next)
    
    def movet(self, dt):
        """
        Shift all times by a constant

        Parameters
        ----------
        dt : float
            the shift to apply to everything

        Notes
        -----
        Use not recommended, since this is O(n).
        """
        curnode = self.head.next
        while curnode:
            curnode.t += dt
            curnode = curnode.next
            
    def pop(self):
        """
        Remove and return the first element (the one with smallest t).

        Returns
        -------
        t : float
            the time associated with the element
        data : object
            the element's data

        See also
        --------
        remove, insert
        """
        self.checkNotEmpty()
        popped = self.head.next
        self.head.next = popped.next
        return (popped.t, popped.data)
        
    def remove(self, t, tmax=None):
        """
        Remove the element(s) associated with the given (span of) time

        If only one time is given, we search for that exact time. If an
        interval is specified (c.f. `!tmax`), all nodes with ``t <= node.t <
        tmax`` are removed.

        Parameters
        ----------
        t : float
            the time to search for
        tmax : float (optional)
            the upper limit of the interval

        Raises
        ------
        RuntimeError
            if only `!t` was specified (i.e. search for an exact time), but it
            was not found. Specifying an interval that turns out to be empty is
            considered deliberate and thus does not raise an error.

        See also
        --------
        removeData, insert
        """
        tnode = self.lastNodeBefore(t)
        
        if tmax is None:
            tmaxnode = tnode.next
            if tmaxnode is None or tmaxnode.t != t:
                raise RuntimeError("time {} not found".format(t))
        else:
            tmaxnode = self.lastNodeBefore(tmax, tnode)
        tnode.next = tmaxnode.next # Hooray for garbage collection
        
    def removeData(self, data):
        """
        Remove the node containing given data

        Parameters
        ----------
        data : <arbitrary>
            the data to search for. Comparison is done using ``is`` (i.e.
            identity check).

        Raises
        ------
        ValueError
            if the wanted data is not found

        See also
        --------
        remove, insert
        """
        curnode = self.head
        while curnode.next and (curnode.next.data is not data):
            curnode = curnode.next
        try:
            curnode.next = curnode.next.next
        except AttributeError: # Didn't find the specified data (curnode.next is None)
            raise ValueError("Could not find specified data")
