"""
                NESTED PROPERTY EXAMPLE
The following is an example of how you can nest multiple property inferences under the same simple class and register them for use
The key Difference is rather than defining the SimplePredictorParamters in the Simple Predictor Class we abstracte it as Predictor Class
and enable the setting then passing of the parameters to the Simple Predictor class.

the benefits of this approach is the checkpoints live in separate library paths the downside is that the properties are not generated as
as part of the same command call or request.
"""

import os
import torch
import numpy as np
from typing import List, Union, Dict, Any
from pydantic.v1 import Field
from openad_service_utils import (
    SimplePredictor,
    SimplePredictorMultiAlgorithm,
    PredictorTypes,
    DomainSubmodule,
    PropertyInfo,
)
from openad_service_utils import start_server
from load import load_smi_ted

# Example Classifier  / Model Import
# -----------------------USER MODEL LIBRARY-----------------------------------
from property_classifier import ClassificationModel

#   USER SETTINGS SECTION
#  import from the nested_parameters.py  library individual Parameters or Paramater sets you wish to use

from nested_parameters import (
    NestedParameters1,
    NestedParameters2,
    NESTED_DATA_SETS,
    get_property_list,
)


class MySimplePredictor(SimplePredictor):
    """Class for your Predictor based on Single Predictor to support multiple"""

    """ The following Properties are important they define your bucket path if you are using a model
    in the property generation. the path on disk or in your bucket would be as follows

    domain/algrithm_name/algorithm_application/algorithm_version/
    e.g as below
    /molecules/myproperty/MySimplePredictor/v0

    Note: the algorithm application name and down on first call of the predictor wil lcheck for existance locally
     of the model checkpoint and its entire directory dtruction under the algorithm application name.
    """
    domain: DomainSubmodule = DomainSubmodule("molecules")
    algorithm_name: str = "myproperty"
    algorithm_application: str = "MySimplePredictor"
    algorithm_version: str = "v0"

    # defines the type of predicTor (CRYSTAL/PROTEIN/MOLECULE)
    property_type: PredictorTypes = PredictorTypes.MOLECULE

    # In the below you can define the valid properties
    available_properties: List[PropertyInfo] = [
        PropertyInfo(name="BACE", description=""),
        PropertyInfo(name="ESOL", description=""),
    ]
    # Note: in this example all of the above parameters get over written on registering of class
    # At registeration you have the option

    # User provided params for api / model inference
    # If not re-speficied in the in the registration process in the case New Parameters are passed the metadata will not be passed bach
    # with service definition to the openad toolkit but will be available to the application

    batch_size: int = Field(description="Prediction batch size", default=128)
    workers: int = Field(description="Number of data loading workers", default=8)
    device: str = Field(description="Device to be used for inference", default="cpu")

    def setup(self):
        # setup your model
        print("Setting up model on >> model filepath: ", self.get_model_location())
        self.model_path = self.get_model_location()  # load model
        # ---------------------------------------------------------------------------
        self.tokenizer = []
        self.model = None
        # ---------------------------------------------------------------------------

    def predict(self, sample: Any):
        """run predictions on your model"""

        ## ------------------------- USER LOGIC HERE -------------------------------------------
        if not self.model:
            self.model = ClassificationModel(
                model=self.algorithm_application, model_path=self.model_path, tokenizer=self.tokenizer
            )
            self.model.to(self.device)
        result = self.model.eval(self.get_selected_property())
        # -----------------------------------------------------------------------------------------
        return result


class MySimplePredictorCombo(SimplePredictorMultiAlgorithm):
    """Class for your Predictor based on Combo Predictor to support multiple"""

    """ The following Properties are important they define your bucket path if you are using a model
    in the property generation. the path on disk or in your bucket would be as follows

    domain/algrithm_name/algorithm_application/algorithm_version/
    e.g as below
    /molecules/myproperty/MySimplePredictor/v0

    Note: the algorithm application name and down on first call of the predictor wil lcheck for existance locally
     of the model checkpoint and its entire directory dtruction under the algorithm application name.
    """

    domain: DomainSubmodule = DomainSubmodule("molecules")
    algorithm_name: str = "myproperty"
    algorithm_application: str = "MySimplePredictorCombo"
    algorithm_version: str = "v0"
    property_type: PredictorTypes = PredictorTypes.MOLECULE
    # OPTIONAL (available_properties). Use only if your class implements many models the user can choose from.
    available_properties: List[PropertyInfo] = [
        PropertyInfo(name="BACE", description=""),                                   
        PropertyInfo(name="ESOL", description=""),
    ]

    # Note: in this example all of the above parameters get over written on registering of class
    # At registeration you have the option
    # ------------------------- USER VARIABLES NOT TO BE EXPOSED TO CLIENT HERE -------------------------------------------
    # User provided params for api / model inference
    # If not re-speficied in the in the registration process in the case New Parameters are passed the metadata will not be passed bach
    # with service definition to the openad toolkit but will be available to the application

    # user proviced params for api / model inference
    batch_size: int = Field(description="Prediction batch size", default=128)
    workers: int = Field(description="Number of data loading workers", default=8)
    device: str = Field(description="Device to be used for inference", default="cpu")

    def setup(self):
        self.models = {}
        tokenizer = []
        if self.get_selected_property() not in self.models:
            self.models[self.get_selected_property()] = ClassificationModel(
                self.get_selected_property(),
                model_path=self.get_model_location(),
                tokenizer=tokenizer,
            )
        print(f"Setting up model {self.get_selected_property()} on >> model filepath: {self.get_model_location()}")

    def predict(self, sample: Any) -> str | float | int | list | dict:
        """ get chkpt and vocab filename and location for current property """
        pt_dir = self.get_model_location()
        try:
            if not os.path.isdir(pt_dir):
                raise FileNotFoundError(f"Directory '{pt_dir}' does not exist.")
            pt_file_list = [f for f in os.listdir(pt_dir) if f.endswith('.pt') and os.path.isfile(os.path.join(pt_dir, f))]
            if not pt_file_list:
                raise FileNotFoundError(f"No checkpoint file '{pt_dir}'.")
            pt_file = pt_file_list[0]
            vocab_file_list = [f for f in os.listdir(pt_dir) if f.endswith('.txt') and os.path.isfile(os.path.join(pt_dir, f))]
            if not vocab_file_list:
                raise FileNotFoundError(f"No vocab/txt file '{pt_dir}'.") 
            vocab_file = vocab_file_list[0]
        except FileNotFoundError as e:
            print(f"Wrapper Setup Error: {e}")
        """ lock and load model for current property """
        self.smi_ted_model = load_smi_ted(ckpt_filename=pt_file, vocab_filename=vocab_file, folder=pt_dir)
        self.smi_ted_model.eval()
        """ execute and return smi-ted analysis results """
        df_test_emb = self.smi_ted_model.encode([sample])
        torch_emb = torch.tensor(df_test_emb.values)
        outputs: np.ndarray = self.smi_ted_model.net(torch_emb).cpu().detach().numpy()
        print(f"{outputs.tolist()=}")
        return outputs.tolist()

for key, value in NESTED_DATA_SETS.items():
    props = NestedParameters2()
    props.set_parameters(
        algorithm_name="smi_ted", algorithm_application=key, available_properties=get_property_list(value)
    )
    MySimplePredictorCombo.register(props, no_model=False)

# start the service running on port 8080
if __name__ == "__main__":
    # start the server
    start_server(port=8080)
