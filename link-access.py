from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterNumber
from qgis.core import QgsProcessingParameterField
from qgis.core import QgsProcessingParameterFeatureSource
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterCrs
from qgis.core import QgsProcessingParameterFeatureSink
from qgis.core import QgsProcessingParameterDefinition
from qgis.core import QgsExpression
import processing


class Linkaccess(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource('candidatelinks', 'Candidate links', types=[QgsProcessing.TypeVectorLine], defaultValue=None))
        self.addParameter(QgsProcessingParameterField('candidateid', 'Candidate ID', type=QgsProcessingParameterField.Any, parentLayerParameterName='candidatelinks', allowMultiple=False, defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('mainnetwork', 'Main network', types=[QgsProcessing.TypeVectorLine], defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('startpoints', 'Start point(s)', types=[QgsProcessing.TypeVectorPoint], defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('censuslayer', 'Census layer', types=[QgsProcessing.TypeVectorPoint], defaultValue=None))
        self.addParameter(QgsProcessingParameterField('employment', 'Employment', type=QgsProcessingParameterField.Numeric, parentLayerParameterName='censuslayer', allowMultiple=False, defaultValue=None))
        self.addParameter(QgsProcessingParameterField('population', 'Population', type=QgsProcessingParameterField.Numeric, parentLayerParameterName='censuslayer', allowMultiple=False, defaultValue=None))
        self.addParameter(QgsProcessingParameterNumber('bufferdiametermeter', 'Buffer diameter (meter)', type=QgsProcessingParameterNumber.Double, minValue=0, maxValue=1000, defaultValue=50))
        self.addParameter(QgsProcessingParameterNumber('isochronediametermeter', 'Isochrone diameter (meter)', type=QgsProcessingParameterNumber.Double, minValue=0, maxValue=5000, defaultValue=400))
        param = QgsProcessingParameterCrs('defaultcrs', 'Default CRS', optional=True, defaultValue='EPSG:4326')
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)
        param = QgsProcessingParameterCrs('projectedcrs', 'Projected CRS', optional=True, defaultValue='EPSG:32756')
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)
        self.addParameter(QgsProcessingParameterFeatureSink('Output', 'Output', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, defaultValue=None))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(9, model_feedback)
        results = {}
        outputs = {}

        # Union
        alg_params = {
            'INPUT': parameters['candidatelinks'],
            'OVERLAY': parameters['mainnetwork'],
            'OVERLAY_FIELDS_PREFIX': '',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Union'] = processing.run('native:union', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        # List unique values
        alg_params = {
            'FIELDS': parameters['candidateid'],
            'INPUT': parameters['candidatelinks']
        }
        outputs['ListUniqueValues'] = processing.run('qgis:listuniquevalues', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        # Reproject layer
        alg_params = {
            'INPUT': outputs['Union']['OUTPUT'],
            'TARGET_CRS': parameters['projectedcrs'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ReprojectLayer'] = processing.run('native:reprojectlayer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}

        # Service area (from layer)
        alg_params = {
            'DEFAULT_DIRECTION': 2,
            'DEFAULT_SPEED': 50,
            'DIRECTION_FIELD': '',
            'INCLUDE_BOUNDS': False,
            'INPUT': outputs['ReprojectLayer']['OUTPUT'],
            'SPEED_FIELD': '',
            'START_POINTS': parameters['startpoints'],
            'STRATEGY': 0,
            'TOLERANCE': 0,
            'TRAVEL_COST2': (parameters['isochronediametermeter']-parameters['bufferdiametermeter']),
            'VALUE_BACKWARD': '',
            'VALUE_BOTH': '',
            'VALUE_FORWARD': '',
            'OUTPUT_LINES': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ServiceAreaFromLayer'] = processing.run('native:serviceareafromlayer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(4)
        if feedback.isCanceled():
            return {}

        # Buffer
        alg_params = {
            'DISSOLVE': False,
            'DISTANCE': parameters['bufferdiametermeter'],
            'END_CAP_STYLE': 0,
            'INPUT': outputs['ServiceAreaFromLayer']['OUTPUT_LINES'],
            'JOIN_STYLE': 0,
            'MITER_LIMIT': 2,
            'SEGMENTS': 5,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Buffer'] = processing.run('native:buffer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(5)
        if feedback.isCanceled():
            return {}

        # Delete holes
        alg_params = {
            'INPUT': outputs['Buffer']['OUTPUT'],
            'MIN_AREA': 0,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['DeleteHoles'] = processing.run('native:deleteholes', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(6)
        if feedback.isCanceled():
            return {}

        # Reproject layer
        alg_params = {
            'INPUT': outputs['DeleteHoles']['OUTPUT'],
            'TARGET_CRS': parameters['defaultcrs'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ReprojectLayer'] = processing.run('native:reprojectlayer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(7)
        if feedback.isCanceled():
            return {}

        # Join attributes by location (summary)
        alg_params = {
            'DISCARD_NONMATCHING': True,
            'INPUT': outputs['ReprojectLayer']['OUTPUT'],
            'JOIN': parameters['censuslayer'],
            'JOIN_FIELDS': [parameters['employment'],parameters['population']],
            'PREDICATE': [0,1,5],
            'SUMMARIES': [5],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['JoinAttributesByLocationSummary'] = processing.run('qgis:joinbylocationsummary', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(8)
        if feedback.isCanceled():
            return {}

        # Field calculator
        alg_params = {
            'FIELD_LENGTH': 11,
            'FIELD_NAME': 'link_id',
            'FIELD_PRECISION': 2,
            'FIELD_TYPE': 2,
            'FORMULA': outputs['ListUniqueValues']['UNIQUE_VALUES'],
            'INPUT': outputs['JoinAttributesByLocationSummary']['OUTPUT'],
            'NEW_FIELD': True,
            'OUTPUT': parameters['Output']
        }
        outputs['FieldCalculator'] = processing.run('qgis:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Output'] = outputs['FieldCalculator']['OUTPUT']
        return results

    def name(self):
        return 'Link-Access'

    def displayName(self):
        return 'Link-Access'

    def group(self):
        return 'Bahman'

    def groupId(self):
        return 'Bahman'
        
    def shortHelpString(self):
        return """<html><body><h2>Algorithm description</h2>
<p>This algorithm generates isochrones for a potential added link form specified point(s) and summarized the catchment opportunities. </p>
<h2>Input parameters</h2>
<h3>Verbose logging</h3>
<p></p>
<h3>Buffer diameter (meter)</h3>
<p>The offset distance form the network service area. </p>
<h3>Candidate ID</h3>
<p>Specify the link's id field.</p>
<h3>Candidate links</h3>
<p>Select the potential link(s) layer.</p>
<h3>Census layer</h3>
<p>Select the census/opportunities layer</p>
<h3>Default CRS</h3>
<p>The output CRS.</p>
<h3>Employment</h3>
<p>Select the employment field.</p>
<h3>Isochrone diameter (meter)</h3>
<p>The travel distance threshold expressing the travel time budget.</p>
<h3>Main network</h3>
<p>Select the main (existing) network.</p>
<h3>Population</h3>
<p>Select the population field.</p>
<h3>Projected CRS</h3>
<p>Select a plane coordinate grid system for your area. The default is set for Sydney/Australia.</p>
<h3>Start point(s)</h3>
<p>Select the origin(s) layer.</p>
<h3>Output</h3>
<p>The output is a set of the ischrone areas for each added potential link. </p>
<h2>Outputs</h2>
<h3>Output</h3>
<p>The output is a set of the ischrone areas for each added potential link. </p>
<br></body></html>"""

    def createInstance(self):
        return Linkaccess()
