from augur import models
from base import ProxyBase, models_to_proxies, model_required


class StaffProxy(ProxyBase):

    def __init__(self, staff_id=None, *args, **kwargs):
        model = None
        if staff_id:
            model = models.Staff[staff_id]

        kwargs['model'] = model
        super(StaffProxy, self).__init__(*args, **kwargs)

    @property
    def _model_class(self):
        return 'Staff'


class WaypointProxy(ProxyBase):

    def __init__(self, *args, **kwargs):
        super(WaypointProxy, self).__init__(*args, **kwargs)

    @property
    def _model_class(self):
        return 'Waypoint'

    @model_required
    def get_first_state(self):
        if not self.model.states:
            return None

        initial = None
        for s in self.model.states:
            if s.is_initial_state:
                initial = s

        if not initial:
            # there is none marked as the initial state so just order by state_order then
            #   select the first one.
            initial = self.model.states.order_by(asc(WaypointStateInstance.state_order)).first()

        return initial


class JourneyProxy(ProxyBase):

    def __init__(self, journey_id=None, *args, **kwargs):
        model = None
        if journey_id:
            model = models.Journey[journed_id]

        kwargs['model'] = model,
        super(JourneyProxy, self).__init__(*args, **kwargs)

    def get_current_position(self):
        """
        Gets the current position by getting the most recent arrived at position object.
        :return: {JourneyPosition|None}
        """
        asset(self.model)
        return self.model.positions.order_by(desc(Position.arrive_time)).first()

    def post_model_create(self, model):
        # Get the first waypoint, that will be our initial position
        first_waypoint = model.path.first_waypoint

        # Once the journey has been created, create the initial
        #   position.
        position = models.JourneyPosition(
            journey=model,
            waypoint=first_waypoint,
            arrive_time=datetime.datetime.now(),
            change_type=ChangeType.first,
            waypoint_percent_complete=0)

        model.starting_position = position

        orm.commit()

    @property
    def _model_class(self):
        return 'Journey'


class PathProxy(ProxyBase):

    def __init__(self, path_id=None, *args, **kwargs):

        model = None
        if path_id:
            model = models.Path[path_id]

        kwargs['model'] = model
        super(PathProxy, self).__init__(*args, **kwargs)

    @models_to_proxies
    def start_journey(self, owner=None, artifact=Nonez):
        if not self.path:
            set_error("You must first instantiate a path before creating a journey")
            return None

        journey = JourneyProxy()
        return journey.create_model(path=self.model, owner=owner, artifacts=artifact)

    @property
    def _model_class(self):
        return 'Path'
