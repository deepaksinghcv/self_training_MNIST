import argparse
from logger import *
from configReader import *
import torch
import torchvision.datasets as datasets
import torchvision.transforms as transforms
from model import MNIST_Model
from tqdm import tqdm
import matplotlib.pyplot as plt
from sklearn.metrics import accuracy_score

'''
TODO:
        add self-training wrapper
'''
def self_train(cfg, logger):
    '''contains code to self-train'''

    logger.info("config content below")
    logger.info(cfg)

    #specify transformations
    transform = transforms.Compose(
        [
            transforms.ToTensor(),
            #transforms.Normalize((0.5),(0.5))
        
        ]
    )

    logger.info("loading MNIST dataset")
    #get the dataset
    initial_train_set = datasets.MNIST('./data', train = True, download = True, transform = transform)
    test_set = datasets.MNIST('./data', train = False, download = True, transform = transform)
    logger.info("loaded MNIST dataset")


    logger.info(f"splitting the dataset")
    #split the train-set into train and validation with some ratio
    train_split_percentage = cfg["self_train"]["train_split"]
    initial_train_set_size = len(initial_train_set)
    needed_train_set_size = int(train_split_percentage * initial_train_set_size)
    needed_val_set_size = initial_train_set_size - needed_train_set_size

    train_set, val_set = torch.utils.data.random_split(initial_train_set, (needed_train_set_size, needed_val_set_size))
    logger.info(f"dataset split")

    
    logger.info(f"train set size: {len(train_set)}")
    logger.info(f"val set size: {len(val_set)}")
    logger.info(f"test set size: {len(test_set)}")


    #prepare the data loader
    logger.info("preparing data loaders")
    train_loader = torch.utils.data.DataLoader(train_set, batch_size = cfg["model_params"]["train_batch_size"], shuffle = True, num_workers = 4)
    val_loader = torch.utils.data.DataLoader(val_set, batch_size = cfg["model_params"]["val_batch_size"], shuffle = True, num_workers = 4)
    test_loader = torch.utils.data.DataLoader(test_set, batch_size = cfg["model_params"]["test_batch_size"], shuffle = True, num_workers = 4)
    logger.info("prepared data loaders")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    processing_on = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("processing on: " + processing_on)
    
    #declare the model
    model = MNIST_Model(num_of_input_channels = cfg["model_params"]["input_features"], num_of_output_channels = cfg["model_params"]["output_features"])

    #move the model to processing unit
    model.to(device)

    #choose an optimizer
    optimizer = torch.optim.SGD(model.parameters(), lr = cfg["hyperparameters"]["learning_rate"])
    
    #define the loss function
    loss_criterion = torch.nn.CrossEntropyLoss()


    #starting self-training loop
    self_train_epochs = len(val_set)//cfg["self_train"]["batch_size"]
    
    logger.info(f"number of self-train-epochs: {self_train_epochs}")
    logger.info("beginning self-training loop")
    for self_train_epoch in tqdm(range(self_train_epochs)):
        #train the model on train_set
        model.train()
        
        train_loss_value_list = []
        for train_epoch in tqdm(range(cfg["hyperparameters"]["epochs"])):
            #for each epoch
            overall_train_batch_loss = 0
            for input, ground_truth_labels in tqdm(train_loader):
                #for each batch 
                input = input.to(device)

                # ground_truth_labels = ground_truth_labels.float()
                ground_truth_labels = ground_truth_labels.to(device)
                # ground_truth_labels = ground_truth_labels + 1

                input = torch.reshape(input, (cfg["model_params"]["batch_size"],-1))
                # print(input.size())
                
                #clear the gradient so they do not accumulate
                optimizer.zero_grad()

                predicted_labels = model(input)

                loss = loss_criterion(predicted_labels, ground_truth_labels)
                
                # logger.debug(loss.item())
                overall_train_batch_loss += float(loss.cpu().item())
                #back-propagation
                loss.backward()

                #optimization step (descent step)
                optimizer.step()
                
                # break
            # break
            logger.debug(f"self_train_epoch: {self_train_epoch + 1}/{self_train_epochs} : train_epoch: {train_epoch + 1} : loss: {overall_train_batch_loss}")
            train_loss_value_list.append(overall_train_batch_loss)

        # #save the model
        # if cfg["project_params"]["to_save_model"]:
        #     torch.save(model.state_dict(), cfg["project_params"]["model_save_location"])


        #test the model on test_set
        model.eval()
        with torch.no_grad():
            self_train_running_test_acc = []
            accuracy_total = 0
            for input, ground_truth_labels in tqdm(test_loader):
                #for each batch 
                input = input.to(device)
                ground_truth_labels = ground_truth_labels.to(device)

                input = torch.reshape(input, (1,-1))
                # print(input.size())
                
                predicted_labels = model(input)

                max_predicted_labels = torch.argmax(predicted_labels, dim = 1, keepdim = True)
                # print("max:", max_predicted_labels)
                # print("gt:", ground_truth_labels)

                accuracy = accuracy_score(ground_truth_labels.cpu(), max_predicted_labels.cpu())
                accuracy_total += accuracy
                
                # break
            accuracy_avg = accuracy_total / (len(test_loader))
            self_train_running_test_acc.append(accuracy_avg)
            logger.debug(f"self_train_epoch: {self_train_epoch + 1}/{self_train_epochs} : average_accuracy: {accuracy_avg}")


        #validate the model on val_set and choose cfg["self_train"]["batch_size"] images from it and
        #move it to train_set by keeping the prediction as groundtruth label in the train_set
        model.eval()
        with torch.no_grad():
            pass
            #TODO: ADD validation code and movement of data to train_set
    
    #ending self-training loop


    # #plot necessary graphs
    # fig, ax = plt.subplots()
    # x_axis = list(torch.arange(1, len(train_loss_value_list) + 1).numpy())
    # line1, = ax.plot(x_axis, train_loss_value_list , 
    #             color='r',
    #             label='loss')

    # plt.xticks(x_axis)
    # plt.xlabel("Epochs")
    # plt.ylabel("Loss")
    # ax.legend()
    # plt.plot()
    # plt.savefig("epoch_vs_loss.png")
    # logger.info("saved the epoch_vs_loss image")


if __name__ == "__main__":
    
    #parse the arguments using argparse module
    parser = argparse.ArgumentParser(description="self-training on MNIST self_train.py")
    parser.add_argument(
        '--config',
        type = str,
        help='location of the yaml configuration file'
    )
    args = parser.parse_args()

    #get the configuration file
    config = ConfigReader(args.config)
    cfg = config.getConfig()

    #setup the logging methods
    log_config = cfg["logging"]
    log_root_obj = CustomLogger(log_config)
    logger = log_root_obj.getLogger()
    self_train(cfg,logger)