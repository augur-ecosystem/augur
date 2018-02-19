#
# def xsl(sep, iterable, quoted_items=False):
#     """
#     Creates a comma separated list from a given list or tuple
#     :param sep: The separator to use between the items in the list.
#     :param quoted_items: True to put quotes around each item in the iterable.
#     :param iterable: The iterable
#     :return: A string
#     """
#     if quoted_items:
#         iterable = ['"%s"' % x for x in iterable]
#     return sep.join(iterable)
#
#
# def ssl(iterable,quoted_items=False):
#     """
#     Creates a space spearated list from the iterable.
#     :param iterable:
#     :param quoted_items:
#     :return:
#     """
#     return xsl(' ', iterable, quoted_items=quoted_items)
#
#
# def csl(iterable, quoted_items=False):
#     """
#     Creates a comma separated list from a given list or tuple
#     :param quoted_items: True to put quotes around each item in the iterable.
#     :param iterable: The iterable
#     :return: A string
#     """
#     return xsl(',', iterable, quoted_items=quoted_items)
#
#
# class QueryBuilder():
#     pass
#
#
# class QueryExpression(object):
#
#     def __init__(self, *args, **kwargs):
#         self.children = []
#         self.parent = None
#         self.expression_str = args[0] if len(args) > 0 else ""
#         self.positional = args[1:] if len(args) > 1 else []
#         self.keywords = kwargs
#
#     def __str__(self):
#         if self.children:
#             return "(%s)"%(reduce(lambda x, y: str(x)+str(y),self.children, ""))
#         else:
#             return self.expression_str.format(*self.positional,**self.keywords)
#
#     def child(self, child_expression):
#         self.children.append(child_expression)
#
#     def And(self):
#         self.children.append(And())
#
#
# def qe(*args, **kwargs):
#     """
#     Shortcut for creating a singular query expression with the given values (see QueryExpression)
#     :param args:
#     :param kwargs:
#     :return:
#     """
#     return QueryExpression(*args,**kwargs)
#
#
# def ca(*args):
#     """
#     Creates a compound query expression and returns the QueryExpression with children connected with AND
#     :param args: The expressions as strings as positional arguments
#     :return: A QueryExpression containing children in number equal to the parameter count to this function
#     """
#     q = qe()
#     for a in args:
#         q.child(qe(a))
#         q.And()
#     return q
#
#
# class QueryExpressionConnector(object):
#
#     def __init__(self, connector_str, *args, **kwargs):
#         self.connector_str = connector_str
#         self.positional = args
#         self.keywords = kwargs
#
#     def __str__(self):
#         return " %s "%self.connector_str.format(*self.positional, **self.keywords)
#
#
# class And(QueryExpressionConnector):
#     def __init__(self):
#         super(And, self).__init__("and")
#
#
# class Or(QueryExpressionConnector):
#     def __init__(self):
#         super(Or, self).__init__("or")
#
#
# class JqlQueryBuilder(QueryBuilder):
#
#     def __init__(self):
#         self.expressions = []
#
#     def __str__(self):
#         return reduce(lambda x,y: str(x)+str(y), self.expressions, "")
#
#     def s(self, *args):
#         qe = QueryExpression()
#         for q in args:
#             qe.add_child(q)
#
#     def q(self, expression, *args, **kwargs):
#         if isinstance(expression,QueryExpression):
#             self.expressions.append(expression)
#         else:
#             self.expressions.append(QueryExpression(expression, *args, **kwargs))
#
#         return self
#
#     def And(self):
#         self.expressions.append(And())
#         return self
#
#     def Or(self):
#         self.expressions.append(Or())
#         return self
#
#     def projects(self,projects):
#         if not isinstance(projects,(list,tuple)):
#             projects = [projects]
#         self.expressions.append(QueryExpression("project in ({projects})", projects=csl(projects)))
#
#     def issuetype(self,types):
#         if not isinstance(types,(list,tuple)):
#             types = [types]
#         self.expressions.append(QueryExpression("issuetype in ({types})", types=csl(types)))
#
#     def resolution(self,resolutions):
#         if not isinstance(resolutions,(list,tuple)):
#             resolutions = [resolutions]
#         self.expressions.append(QueryExpression("resolution in ({resolutions})", resolutions=csl(resolutions)))
#
#     def assignee(self,assignees):
#         if not isinstance(assignees,(list,tuple)):
#             assignees = [assignees]
#         self.expressions.append(QueryExpression("assignee in ({assignees})", assignees=csl(assignees)))
#
#     def reporter(self,reporters):
#         if not isinstance(reporters,(list,tuple)):
#             reporters = [reporters]
#         self.expressions.append(QueryExpression("reporter in ({reporters})", reporters=csl(reporters)))
#
#
# if __name__ == '__main__':
#
#     q = QueryExpression()
#     q.add_child(QueryExpression("issuetype=story"))
#     q.add_child(Or())
#     q.add_child(QueryExpression("resolution=fixed"))
#
#     jql = JqlQueryBuilder().query("project in ({projects})",projects=csl(['eng','def'])).And().query("reporter={0}","kshehadeh")
#     jql.And().query(q)
#     print str(jql)
#
#
#     jql.q(qe("project in ({projects})",projects=csl(['eng','def']))).And().q(c("issuetype=story","resolution=fixed"))
#
#
#     j = JqlQueryBuilder().projects(["eng","def"])._and().issuetype(["story"])._or()[reporter(["kshehadeh"]),resolution(["fixed"]))]