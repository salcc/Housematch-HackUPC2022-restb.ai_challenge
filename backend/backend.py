# -*- coding: utf-8 -*-
"""restbaiAPI_HackUPC.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1mmhZD-5gxV8vjiDumqcmCMGSMt8YgQKM

Urls
"""

import requests 
import json
import pickle
from sklearn.ensemble import RandomForestClassifier
from scipy import spatial
import copy
import numpy as np
import time 
from pkl import load_data, save_data

rb_models = ['re_roomtype_international', 're_exterior_styles', 're_features_v3', 're_appliances_v2', 're_kitchen_finishes', 're_bathroom_features', 're_condition', 'caption']
restbai_url = 'https://api-us.restb.ai/vision/v2/multipredict'

"""Coses importants dels models:
Perquè el model exterior styles rebi fotos adients passar-li les classificades com a front_house per re_roomtype_global_v2 o outdoor house per re_roomtype_international, si multirequest no cal ja classifica a no_front_house. Global= us, international = resta del món. Utilitzarem l'international.

Utils
"""

def concat_stringlist(stringlist):
  '''Recieves a list of strings and returns it concatenated in a single string
  with positions separated by commas. Linear cost. Stringlist can't be empty'''
  total_st = stringlist[0]
  for i in range(1, len(stringlist)):
    total_st+=','+stringlist[i]
  return total_st

#counter dict utils 
def is_nullcounterdict(counterdict, tuple = False):
  '''Given a counterdict which can have dim2 tuples as values the function
  tells whether it's null or not.'''
  for key in counterdict:
    if (not tuple and counterdict[key]!=0):
      return False 
    if (tuple and counterdict[key]!=(0,0)):
      return False 
  return True

def normalize_counter_dict(counterdict):
  acum = 0
  for key in counterdict:
    acum+= counterdict[key]
  for key in counterdict:
    counterdict[key]/acum

#Score functions (scalated from 0 to 10), all run in constant time
def documentation_score(n_2D,n_3D, energy, map_location):
  '''Score for how well documented an online house post is, each milestone earns points.'''
  #predef bonuses:
  hasplan = 3
  bothplans = 2
  hasmaploc = 1
  hasenergydesc = 2
  min_score = 0
  max_score = 10
  
  score = min_score
  
  if (n_2D!=0 or n_3D!=0):
    score +=hasplan
    if (n_2D>0 and n_3D>0):
      score += bothplans
  if (map_location>0):
    score+=hasmaploc
  if (energy >0):
    score+=hasenergydesc
  if score == hasplan+bothplans+hasmaploc+hasenergydesc:
    score = max_score
  return score


def exterior_1_score(n_balcony, n_terrace):
  '''Score for balcony and terrace, each milestone earns points.'''
  has_balcony = 3
  has_terrace = 3
  mult_terraces = 3
  min_score = 0
  max_score = 10

  score = min_score
  if (n_balcony>0):
    score+=has_balcony
  if (n_terrace>0):
    score+=has_terrace
    if (n_terrace>1):
      score+=mult_terraces
  if (score == has_balcony+has_terrace+mult_terraces):
    score = max_score
  return score

def exterior_2_score(n_pool, n_garden):
  '''Score for pools and gardens, each milestone earns points.'''
  has_pool = 4
  has_garden = 4
  min_score = 0
  max_score = 10

  score = min_score
  if (n_pool>0):
    score +=has_pool
  if (n_garden>0):
    score += has_garden
  if (score == has_pool + has_garden):
    score = max_score
  return score



def outdoor_view(mountain_view, ocean_view):
  '''It's always nice to have good views, trivial score function'''
  has_mountain_view = 5
  has_ocean_view = 5
  score = 0
  if (mountain_view>0):
    score+=has_mountain_view
  if (ocean_view>0):
    score+=has_ocean_view
  return score

def utils_score_1(n_gym, n_office, n_parking):
  '''Important utils score'''
  min_score = 0
  max_score = 10
  has_gym = 3
  has_office = 3
  has_parking = max_score- has_gym-has_office
  score = min_score
  if (n_gym>0):
    score +=has_gym
  if (n_office>0):
    score+=has_office
  if (n_parking>0):
    score+=has_parking
  return score

def utils_score_2(n_cellar, n_loundry_room, n_storage_pantry):
  '''Non important utils score'''
  min_score = 0
  max_score = 10
  cellarbonus = 1
  loundrybonus = 3
  storagebonus = 3
  score = min_score
  return cellarbonus+loundrybonus+storagebonus



def normalize_and_correlate(general_dict, sp_dict, listformat = False):
  '''Given a general dictionary and a specific dictionary of counters for a property it applies a normalization
  process and computes a correlation measure to compute a metric that the larger it is the more similar the 
  proportions are. We set listformat = True if the dict contains 1x2 lists. In a future update it would be nice
  to normalized also based on the info of the second parameter on the list.'''

  totalsum_general = 0
  totalsum_sp = 0
  for label in general_dict:
    if (not listformat):
      totalsum_general+=general_dict[label]
      totalsum_sp+=sp_dict[label]
    else:
      totalsum_general+=general_dict[label][0]
      totalsum_sp+=sp_dict[label][0]

  normalized_list_gen = []
  normalized_list_sp = []

  for label in general_dict:
    if (not listformat):
      if totalsum_general!=0:
        normalized_list_gen.append(general_dict[label]/totalsum_general)
      else:
        normalized_list_gen.append(0)

      if totalsum_sp!=0:
        normalized_list_sp.append(sp_dict[label]/totalsum_sp)
      else:
        normalized_list_sp.append(0)

    else:
      if totalsum_general!=0:
        normalized_list_gen.append(general_dict[label][0]/totalsum_general)
      else:
        normalized_list_gen.append(0)
      if totalsum_sp!=0:
        normalized_list_sp.append(sp_dict[label][0]/totalsum_sp)
      else:
        normalized_list_sp.append(0)
  
  simmilarity = 1 - spatial.distance.euclidean(normalized_list_gen, normalized_list_sp)
  return simmilarity
  
def xprint(arrx):
  counter = 0
  for element in arrx:
    print(counter, element, sep = ' ')
    counter+=1

def update_general_counters(general_property_counters,general_home_features_counters,general_home_appliances_counters,general_kitchen_finishes_counters,general_bathroom_features_counters, property_counters, home_features_counters, home_appliances_counters, kitchen_finishes_counters, bathroom_features_counters):
  '''general_property_counters
  general_home_features_counters
  general_home_appliances_counters
  general_kitchen_finishes_counters
  general_bathroom_features_counters, could be more efficient but was coded at 3am'''

  try:
    for label in property_counters:
      general_property_counters[label]+=property_counters[label]

    for label in home_features_counters:
      general_home_features_counters[label]+=home_features_counters[label]
    
    for label in home_appliances_counters:
      general_home_appliances_counters[label]+= home_appliances_counters[label]

    for label in kitchen_finishes_counters:
      general_kitchen_finishes_counters[label][0]+=kitchen_finishes_counters[label][0]
      general_kitchen_finishes_counters[label][1]+=kitchen_finishes_counters[label][1]

    for label in bathroom_features_counters:
      general_bathroom_features_counters[label][0]+=bathroom_features_counters[label][0]
      general_bathroom_features_counters[label][1]+=bathroom_features_counters[label][1]
  except:
    print("crashed :(")
    return 0
  return 2

def load_general_dict_data():
  with open('general_property_counters.json') as fp:
    general_property_counters = json.load(fp)
  with open('general_home_features_counters.json') as fp:
    general_home_features_counters = json.load(fp)
  with open('general_home_appliances_counters.json') as fp:
    general_home_appliances_counters = json.load(fp)
  with open('general_kitchen_finishes_counters.json') as fp:
    general_kitchen_finishes_counters = json.load(fp)
  with open('general_bathroom_features_counters.json') as fp:
    general_bathroom_features_counters = json.load(fp)
  return general_property_counters, general_home_features_counters, general_home_appliances_counters, general_kitchen_finishes_counters, general_bathroom_features_counters


def save_general_dict_data(general_property_counters, general_home_features_counters, general_home_appliances_counters, general_kitchen_finishes_counters, general_bathroom_features_counters):
  with open('general_property_counters.json', 'w') as fp:
      json.dump(general_property_counters,fp)
  with open('general_home_features_counters.json', 'w') as fp:
      json.dump(general_home_features_counters,fp)
  with open('general_home_appliances_counters.json', 'w') as fp:
      json.dump(general_home_appliances_counters,fp)
  with open('general_kitchen_finishes_counters.json', 'w') as fp:
      json.dump(general_kitchen_finishes_counters,fp)
  with open('general_bathroom_features_counters.json', 'w') as fp:
      json.dump(general_bathroom_features_counters,fp)

#creating emptyfile for the first time
def create_empty_general():
  property_counters = {"null": 0,"2D_floor_plan":0,"3D_floor_plan":0,"balcony":0,"bathroom":0,"cellar":0,"details":0,"dining_room":0,"documents":0,"empty_room":0,"energy_certificate":0,"garden":0,"gym":0,"hall-corridor":0,"kitchen":0,"laundry_room":0,"living-dining_room":0,"living_room":0,"map_location":0,"mountain_view":0,"non_related":0,"office":0,"outdoor_building":0,"outdoor_house":0,"parking":0,"pool":0,"reception-lobby":0,"room-bedroom":0,"stairs":0,"storage_pantry":0,"terrace":0,"walk_in_closet":0,"water_view": 0}
  home_features_counters = {"null":0,"beamed_ceiling":0,"carpet":0,"ceiling_fan":0,"coffered_ceiling":0,"exposed_bricks":0,"fireplace":0,"french_doors":0,"hardwood_floor":0,"high_ceiling":0,"kitchen_bar":0,"kitchen_island":0,"natural_light":0,"notable_chandelier":0,"skylight":0,"stainless_steel":0,"tile_floor":0,"vaulted_ceiling":0,"ceiling_fan":0,"central_ac":0,"deck":0,"dock":0,"fireplace":0,"fire_pit":0,"french_doors":0,"hot_tub":0,"lawn":0,"mountain_view":0,"outdoor_kitchen":0,"outdoor_living_space":0,"pergola":0,"pool":0,"water_view":0}
  home_appliances_counters = {"null":0,"dishwasher":0,"electric_stovetop":0,"elevator":0,"gas_stovetop":0,"microwave":0,"oven":0,"radiator":0,"baseboard_radiator":0,"range_hood":0,"range_oven":0,"gas_range_oven":0,"electric_range_oven":0,"refrigerator":0,"tv":0,"wall_mounted_ac":0,"washer__dryer":0,"water_heater":0}
  kitchen_finishes_counters = {"null": [0,0],"brown_cabinets":[0,0],"dark_brown_cabinets":[0,0],"dark_countertops":[0,0],"dark_floor":[0,0],"kitchen_island_sink":[0,0],"light_brown_cabinets":[0,0],"light_countertops":[0,0],"light_floor":[0,0],"pendant_lighting":[0,0],"stone_countertops":[0,0],"white_cabinets":[0,0]}
  bathroom_features_counters = {"null": [0,0],"bath":[0,0],"shower":[0,0],"sink":[0,0],"double_sink":[0,0],"vanity":[0,0],"mirror":[0,0],"toilet":[0,0],"combined_bath_shower":[0,0],"shower_door":[0,0],"shower_curtain":[0,0]}
  save_general_dict_data(property_counters, home_features_counters, home_appliances_counters, kitchen_finishes_counters, bathroom_features_counters)


def get_ml_parameters(img_url_list, label, general_property_counters,general_home_features_counters,general_home_appliances_counters,general_kitchen_finishes_counters,general_bathroom_features_counters):
  '''Given the data obtained though the restbaiAPI models returns a fixed set of meaningful numerical parameters
  in the context of the problem from which we intend to train machine learning algorithms.
  
  Function input parameters:
    -> img_url_list: list of urls corresponding to a single property
    -> label: corresponding to the like or dislike made by the user to the property
       {PROFILE USR COUNTERS} indicate the general taste of the usr and will be updated if the label is a like
    -> general_property_counters: general version of local property_counters
    -> general_home_features_counters: general version of local home_features_counters
    -> general_home_appliances_counters: general version of local home_appliances_counters
    -> general_kitchen_finishes_counters: general version of local kitchen_finishes_counters
    -> general_bathroom_features_counters: general version of local bathroom_features_counters

  Returned ML parameters (numpy array) the fixed position values are:
   ->doc pending, see varnames at the end of the file

  How it works:
  input->restb_ai (feature extraction) -> parameter computation (our own algorithm working with dictionaries represe
  nting counters which we normalize obtaining proportions to compare them with the global normalized counters of the user)
  '''

  #restb_ai API link and model nmes
  rb_models = ['re_roomtype_international', 're_exterior_styles', 're_features_v3', 're_appliances_v2', 're_kitchen_finishes', 're_bathroom_features', 're_condition', 'caption']
  restbai_url = 'https://api-us.restb.ai/vision/v2/multipredict'

  #thresholds used in significance decisions
  threshold_roomtype = 0.5
  threshold_exteriortype = 0.5

  #counter dictionary declaration
  #for simplicity purposes the counters in the dictionary will take names as the categories in room type international
  #general counters
  property_counters = {"null": 0,"2D_floor_plan":0,"3D_floor_plan":0,"balcony":0,"bathroom":0,"cellar":0,"details":0,"dining_room":0,"documents":0,"empty_room":0,"energy_certificate":0,"garden":0,"gym":0,"hall-corridor":0,"kitchen":0,"laundry_room":0,"living-dining_room":0,"living_room":0,"map_location":0,"mountain_view":0,"non_related":0,"office":0,"outdoor_building":0,"outdoor_house":0,"parking":0,"pool":0,"reception-lobby":0,"room-bedroom":0,"stairs":0,"storage_pantry":0,"terrace":0,"walk_in_closet":0,"water_view": 0}
  home_features_counters = {"null":0,"beamed_ceiling":0,"carpet":0,"ceiling_fan":0,"coffered_ceiling":0,"exposed_bricks":0,"fireplace":0,"french_doors":0,"hardwood_floor":0,"high_ceiling":0,"kitchen_bar":0,"kitchen_island":0,"natural_light":0,"notable_chandelier":0,"skylight":0,"stainless_steel":0,"tile_floor":0,"vaulted_ceiling":0,"ceiling_fan":0,"central_ac":0,"deck":0,"dock":0,"fireplace":0,"fire_pit":0,"french_doors":0,"hot_tub":0,"lawn":0,"mountain_view":0,"outdoor_kitchen":0,"outdoor_living_space":0,"pergola":0,"pool":0,"water_view":0}
  home_appliances_counters = {"null":0,"dishwasher":0,"electric_stovetop":0,"elevator":0,"gas_stovetop":0,"microwave":0,"oven":0,"radiator":0,"baseboard_radiator":0,"range_hood":0,"range_oven":0,"gas_range_oven":0,"electric_range_oven":0,"refrigerator":0,"tv":0,"wall_mounted_ac":0,"washer__dryer":0,"water_heater":0}

  #specs counters
  #each specs counter has two values, first the number of times it has been detected, second the number of images it was
  #sensible that it could have been detected there (for example we consider that kitchen finishes are sensible to be detected
  #in kitchens)
  
  kitchen_finishes_counters = {"null": [0,0],"brown_cabinets":[0,0],"dark_brown_cabinets":[0,0],"dark_countertops":[0,0],"dark_floor":[0,0],"kitchen_island_sink":[0,0],"light_brown_cabinets":[0,0],"light_countertops":[0,0],"light_floor":[0,0],"pendant_lighting":[0,0],"stone_countertops":[0,0],"white_cabinets":[0,0]}
  bathroom_features_counters = {"null": [0,0],"bath":[0,0],"shower":[0,0],"sink":[0,0],"double_sink":[0,0],"vanity":[0,0],"mirror":[0,0],"toilet":[0,0],"combined_bath_shower":[0,0],"shower_door":[0,0],"shower_curtain":[0,0]}

  #some other metrics
  acum_rc_number = 0
  acum_bd_lvl_score = 0
  acum_bt_lvl_score = 0
  acum_kt_lvl_score = 0

  for img_url in img_url_list:
    current_payload = {
    # Add your client key
    'client_key': '8e1f10a5a185764a16779a64a8573b64a97a5d6a3dfca3b52d73d95e78b3620e',
    'model_id': concat_stringlist(rb_models),
    # Add the image URL you want to classify
    'image_url': img_url}

    # Make the classify request
    response = requests.get(restbai_url, params=current_payload)

    json_response = response.json()


    #references from the json for comfort, model by model
    print(json_response)
    roomtype_international_data = json_response['response']['solutions']['re_roomtype_international']
    roomtype = 'null' #grouping, scores, counters and bonus purpose
    if (roomtype_international_data['top_prediction']['confidence']>threshold_roomtype):
      roomtype = roomtype_international_data['top_prediction']['label']


    #current version does not use this data
    exterior_styles_data = json_response['response']['solutions']['re_exterior_styles'] 
    exterior_type = 'null' #bonuses
    if (exterior_styles_data['top_prediction']['confidence']>threshold_exteriortype):
      exterior_type = exterior_styles_data['top_prediction']['label']


    home_features_data = json_response['response']['solutions']['re_features_v3']
    featurelist_home = [] #function + bonuses
    for element in home_features_data['detections']:
      featurelist_home.append(element['label'])
    

    detected_home_appliances = json_response['response']['solutions']['re_appliances_v2']['detections'] #score
    detected_kitchen_finishes= json_response['response']['solutions']['re_kitchen_finishes']['detections'] #score
    detected_bathroom_features = json_response['response']['solutions']['re_bathroom_features']['detections'] #score
    
    room_condition_number = json_response['response']['solutions']['re_condition']['score'] #score
    caption = json_response['response']['solutions']['caption']['description'] #additive
    
    if room_condition_number is None:
      room_condition_number= 0

    acum_rc_number += room_condition_number
    #augmenting counters
    #incrementing generic
    property_counters[roomtype]+=1
    
    if (roomtype == 'room-bedroom'):
      acum_bd_lvl_score+=room_condition_number

    for homefeature in featurelist_home:
      home_features_counters[homefeature]+=1

    for homeapliance in detected_home_appliances:
      home_appliances_counters[homeapliance['label']]+=1

    #incrementing specfs. counters & acums
    if (roomtype == 'kitchen'):
      acum_kt_lvl_score+=1

      for finish_kitchen in detected_kitchen_finishes:
        if (type(finish_kitchen)!=str): #parche necessari per quan no troba
          kitchen_finishes_counters[finish_kitchen['label']][0]+=1
      for key in kitchen_finishes_counters:
        kitchen_finishes_counters[key][1]+=1
    
    if (roomtype == 'bathroom'):
      acum_bt_lvl_score+=1

      for finish_bathroom in bathroom_features_counters:
        if (type(finish_bathroom)!=str): #parche necessari per quan no troba
          bathroom_features_counters[finish_bathroom['label']][0]+=1
      for key in bathroom_features_counters:
        bathroom_features_counters[key][1]+=1
    
    #not implemented yet
    #if the swiping has been positive we update the global counters
    if label == 1: 
      errhandling = update_general_counters(general_property_counters,general_home_features_counters,general_home_appliances_counters,general_kitchen_finishes_counters,general_bathroom_features_counters, property_counters, home_features_counters, home_appliances_counters, kitchen_finishes_counters, bathroom_features_counters)

    time.sleep(0.34)


  #parameter computing
  avg_rc_number = acum_rc_number/len(img_url_list)
  
  stats_bd_lvl_score = 0
  if property_counters['room-bedroom']>0:
    stats_bd_lvl_score = acum_bd_lvl_score/property_counters['room-bedroom']
  
  stats_bt_lvl_score=0
  if property_counters['bathroom']>0:
    stats_bt_lvl_score = acum_bt_lvl_score/property_counters['bathroom']
  
  stats_kt_lvl_score=0
  if property_counters['kitchen']>0:
    stats_kt_lvl_score = acum_kt_lvl_score/property_counters['kitchen']

  docscore = documentation_score(property_counters['2D_floor_plan'],property_counters['3D_floor_plan'], property_counters['energy_certificate'],property_counters['map_location'])
  ext1_score = exterior_1_score(property_counters['balcony'], property_counters['terrace'])
  ext2_score = exterior_2_score(property_counters['pool'], property_counters['garden'])
  outdoor_view_score = outdoor_view(property_counters['mountain_view'], property_counters['water_view'])
  uscore1 = utils_score_1(property_counters['gym'], property_counters['office'], property_counters['parking'])
  uscore2 = utils_score_2(property_counters['cellar'], property_counters['laundry_room'],property_counters['storage_pantry'])  
  bt_lvl_score = normalize_and_correlate(general_bathroom_features_counters,bathroom_features_counters, True)
  kt_lvl_score = normalize_and_correlate(general_kitchen_finishes_counters,kitchen_finishes_counters, True)
  bd2_lvl_score = normalize_and_correlate(general_property_counters,property_counters, False)
  claustrophobyparameter = property_counters['hall-corridor']/len(img_url_list)
  
  #save the updated data
  save_general_dict_data(general_property_counters, general_home_features_counters, general_home_appliances_counters, general_kitchen_finishes_counters, general_bathroom_features_counters)

  x = np.array([float(avg_rc_number), float( stats_bd_lvl_score), float(stats_bt_lvl_score), float( stats_kt_lvl_score), float(docscore), float( ext1_score), float( ext2_score), float( outdoor_view_score), float( uscore1), float( uscore2), float( bt_lvl_score), float(kt_lvl_score), float( bd2_lvl_score), float( claustrophobyparameter)])
  
  return x

def generate_dataset(property_list, labels):
  '''Generates a ml classification dataset from a list of properties being properties a list of urls and given labels which is a list with the swipe result for property i at position i 
  while updating general weight counter parameters used in the score calculations to get the ml parameters.
  
  Properties_list [ [ [prop0_img_0, prop0_img_1, ...] , 'string_id_0' ]]
                  | [ [prop1_img_0, prop1_img_1, ...] , 'string_id_1' ]|  
                  [  ...                                               ]'''
  try:
    general_property_counters, general_home_features_counters, general_home_appliances_counters, general_kitchen_finishes_counters, general_bathroom_features_counters = load_general_dict_data()
  except:
    create_empty_general()
    general_property_counters, general_home_features_counters, general_home_appliances_counters, general_kitchen_finishes_counters, general_bathroom_features_counters = load_general_dict_data()
    
  counter = 0
  x = []
  y = []
  for proprt in property_list:
    print("starting processing of property", counter, sep=' ')
    label = labels[counter]
    x_item = get_ml_parameters(proprt['imgs'], label, general_property_counters,general_home_features_counters,general_home_appliances_counters,general_kitchen_finishes_counters,general_bathroom_features_counters)
    x.append(x_item)
    y.append(label)
    counter+=1

  return x,y



def generate_xtrain(x,y):
  xtrain = []
  ytrain = []
  for i in range(len(y)):
    if y[i] is not None:
      xtrain.append(copy.deepcopy(x[i]))
      ytrain.append(copy.deepcopy(y[i]))
  return xtrain,ytrain

def train_forest_model(xtrain,ytrain):
  '''Given a dataset we load retrain and save our ML model while also returning it'''
  #loads the model
  try:
    model = pickle.load(open('forest.sav', 'rb'))
  except:
    model = RandomForestClassifier(max_depth=2, random_state=0)
  #trains the model
  model.fit(xtrain,ytrain)

  #saves the model
  pickle.dump(model, open('forest.sav', 'wb'))

  #returns the model 
  return model

def make_predictions(model, x, id_list):
  '''Given the model and the dataset for predictions returns a sorted dict by c1 probability with the image url'''
  probs = model.predict_proba(x)
  probdictlist = []
  srclist = []
  counter = 0
  for id in id_list:
    probdictlist.append({"url": id, "prob" : probs[counter][1]})
    counter+=1
  #ordenar probdictlist
  sorted_probdictlist = sorted(probdictlist, key=lambda d: d['prob']) 
  return sorted_probdictlist

def format_sorted_predictions(properties_list, sorted_probdictlist):
  formatted_list = []
  for p in sorted_probdictlist:
    s = ''
    for pl in properties_list:
      if (pl['url']==p['url']):
        s = pl['imgs'][0]
        break
    formatted_list.append({'url':p['url'], 'src':s})
  return formatted_list


def recommendation_button(property_list,y):
  '''Interacts with the recomendation button in the program.'''
  try:
      model = pickle.load(open('forest.sav', 'rb'))
  except:
      model = RandomForestClassifier(max_depth=2, random_state=0)

  idlist = []

  for p in property_list:
    idlist.append(p['url'])

  try:
    x = load_data('x.pkl')
  except:
    return 1
  
  sorted_probdictlist = make_predictions(model,x,idlist)
  sorted_probdictlist = sorted_probdictlist[::-1]
  fsp = format_sorted_predictions(property_list, sorted_probdictlist)
  return fsp

def training_button(property_list, labels):
  '''Trains the current model with the loaded data'''
  try:
    x = load_data('x.pkl')
    y = labels
  except:
    #if encodings not saved construct and save them
    x,y = generate_dataset(property_list, labels)
    save_data(x,'x.pkl')
  
  xtrain,ytrain = generate_xtrain(x,y)
  print(xtrain,ytrain,sep=' ')
  model = train_forest_model(xtrain,ytrain)
